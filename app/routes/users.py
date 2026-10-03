import psycopg2
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth import hash_password, verify_password
from app.database import get_cursor
from app.models import (
    HealthResponse,
    LoginRequest,
    MessageResponse,
    TokenResponse,
    UserCreate,
    UserListResponse,
    UserOut,
)
from app.security import create_access_token, get_current_user

router = APIRouter()

# A real bcrypt hash of a throwaway string, computed once at startup.
#
# When a login arrives for an email that does not exist, the password is checked
# against this instead of returning early. bcrypt takes ~100ms on purpose, so
# returning early for unknown emails would make them answer measurably faster
# than known ones - leaking exactly the information the identical error message
# is there to hide.
_TIMING_EQUALIZER_HASH = hash_password("not-a-real-password-timing-equalizer")


@router.get("/", response_model=MessageResponse)
def root():
    return {"message": "Backend API is running"}


@router.get("/health", response_model=HealthResponse)
def health_check():
    return {"status": "healthy"}


@router.get("/users", response_model=UserListResponse)
def get_users(
    limit: int = Query(default=50, ge=1, le=100, description="How many users to return"),
    offset: int = Query(default=0, ge=0, description="How many users to skip"),
    _current_user: str = Depends(get_current_user),
):
    """List users. Requires a valid bearer token.

    `Depends(get_current_user)` is what locks the door. FastAPI runs that
    dependency before this function body exists, and it raises 401 if the token
    is missing, expired, or not signed by us. Previously this endpoint had no
    dependency at all and returned every account to anyone who asked.

    The leading underscore says we want the authentication check but not the
    value it returns.

    limit and offset cap the work: without them a single request would try to
    load the entire table into memory once the table is large.
    """
    with get_cursor() as cur:
        cur.execute(
            "SELECT id, name, email FROM users ORDER BY id LIMIT %s OFFSET %s",
            (limit, offset),
        )
        rows = cur.fetchall()

    users = [{"id": row[0], "name": row[1], "email": row[2]} for row in rows]
    return {"users": users, "limit": limit, "offset": offset}


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate):
    """Create an account.

    RETURNING hands back the row Postgres just wrote, including the id its
    counter assigned, so no second SELECT is needed to discover it.
    """
    password_hash = hash_password(user.password)
    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO users (name, email, password_hash)
                VALUES (%s, %s, %s)
                RETURNING id, name, email
                """,
                (user.name, user.email, password_hash),
            )
            row = cur.fetchone()
    except psycopg2.errors.UniqueViolation:
        # Postgres rejected a duplicate email. Leaning on the database's unique
        # constraint instead of checking first with a SELECT is what makes this
        # correct under load: two simultaneous signups for the same address
        # cannot both pass, no matter how the timing falls.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    return {"id": row[0], "name": row[1], "email": row[2]}


@router.post("/login", response_model=TokenResponse)
def login(credentials: LoginRequest):
    """Exchange an email and password for a token.

    Both failure modes - no such account, and wrong password - return the same
    status code and the same message. Answering 404 for one and 401 for the
    other let anyone submit a list of email addresses and learn which ones are
    registered here, which is the first step of a credential-stuffing attack.
    """
    with get_cursor() as cur:
        cur.execute(
            "SELECT password_hash FROM users WHERE email = %s",
            (credentials.email,),
        )
        row = cur.fetchone()

    # Verify against the throwaway hash when the email is unknown, so the slow
    # bcrypt comparison happens either way and the two paths take equally long.
    stored_hash = row[0] if row is not None else _TIMING_EQUALIZER_HASH
    password_matches = verify_password(credentials.password, stored_hash)

    if row is None or not password_matches:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "access_token": create_access_token(subject=credentials.email),
        "token_type": "bearer",
    }


@router.get("/me", response_model=UserOut)
def read_me(current_user: str = Depends(get_current_user)):
    """Return the account belonging to whoever owns the token.

    current_user is the email taken from inside the verified token, not from the
    request body, so a caller cannot ask for somebody else's record.
    """
    with get_cursor() as cur:
        cur.execute(
            "SELECT id, name, email FROM users WHERE email = %s",
            (current_user,),
        )
        row = cur.fetchone()

    if row is None:
        # The token is validly signed but its subject is gone - for instance the
        # account was deleted after the token was issued.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return {"id": row[0], "name": row[1], "email": row[2]}
