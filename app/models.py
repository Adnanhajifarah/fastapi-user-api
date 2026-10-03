from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """Request body for creating an account."""

    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    # bcrypt only reads the first 72 bytes of a password; anything beyond that
    # is silently ignored and adds no security. Capping it here makes the limit
    # explicit instead of a surprise.
    password: str = Field(min_length=6, max_length=72)


class LoginRequest(BaseModel):
    """Request body for logging in.

    Deliberately a separate model from UserCreate. Logging in needs an email and
    a password and nothing else - the old code reused UserCreate, which forced
    callers to send a `name` that was then ignored.

    It also must not apply account-creation rules. If the minimum password
    length is raised later, existing users with shorter passwords still have to
    be able to log in.
    """

    email: EmailStr
    # Only an upper bound, to stop a huge body from being fed to bcrypt.
    password: str = Field(min_length=1, max_length=72)


class UserOut(BaseModel):
    """A user as returned by the API.

    There is no password or hash field here at all. Declaring the response shape
    as this type makes leaking a stored hash structurally impossible rather than
    something every endpoint has to remember not to do.
    """

    id: int
    name: str
    email: EmailStr


class UserListResponse(BaseModel):
    """A page of users, plus which page it is.

    The echoed limit and offset let a caller tell where they are without having
    to track it themselves.
    """

    users: list[UserOut]
    limit: int
    offset: int


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MessageResponse(BaseModel):
    message: str


class HealthResponse(BaseModel):
    status: str
