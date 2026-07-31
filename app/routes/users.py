import psycopg2
from fastapi import APIRouter, Depends, HTTPException

from app.database import get_connection
from app.auth import hash_password, verify_password
from app.security import create_access_token, get_current_user
from app.models import User

router = APIRouter()


@router.get("/")
def root():
    return {"message": "Backend API is running"}


@router.get("/health")
def health_check():
    return {"status": "healthy"}


@router.get("/users")
def get_users():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, email FROM users")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    users = [{"id": row[0], "name": row[1], "email": row[2]} for row in rows]
    return {"users": users}


@router.post("/users", status_code=201)
def create_user(user: User):
    conn = get_connection()
    cursor = conn.cursor()
    hashed = hash_password(user.password)
    try:
        cursor.execute(
            "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
            (user.name, user.email, hashed),
        )
        conn.commit()
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        raise HTTPException(status_code=409, detail="Email already registered")
    finally:
        cursor.close()
        conn.close()
    return {"message": "User created"}


@router.post("/login")
def login(user: User):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT password FROM users WHERE email = %s", (user.email,)
    )
    result = cursor.fetchone()
    cursor.close()
    conn.close()

    if result is None:
        raise HTTPException(status_code=404, detail="User not found")

    stored_password = result[0]
    if not verify_password(user.password, stored_password):
        raise HTTPException(status_code=401, detail="Invalid password")

    access_token = create_access_token(subject=user.email)
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me")
def read_me(current_user: str = Depends(get_current_user)):
    """Protected: only reachable with a valid bearer token.

    `current_user` is the email pulled from the verified token, so the route
    returns the record belonging to whoever owns the token.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, email FROM users WHERE email = %s", (current_user,)
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="User not found")
    return {"id": row[0], "name": row[1], "email": row[2]}
