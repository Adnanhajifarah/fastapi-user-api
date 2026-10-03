from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import close_pool
from app.routes.users import router as user_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown hooks.

    Nothing to do on startup - the connection pool builds itself on first use.
    On shutdown, close the pooled connections so Postgres is not left holding
    sockets for a process that has exited.
    """
    yield
    close_pool()


# The title, description and version show up on the /docs page, which is the
# demo surface for this project.
app = FastAPI(
    title="User Management & Authentication API",
    description=(
        "FastAPI and PostgreSQL user API with JWT authentication. "
        "Use POST /login to get a token, then Authorize above to call "
        "protected endpoints."
    ),
    version="0.2.0",
    lifespan=lifespan,
)

app.include_router(user_router)
