# FastAPI User API

A RESTful backend API built with FastAPI and PostgreSQL for user registration,
retrieval, and JWT-based authentication. Passwords are hashed with bcrypt before
storage; login issues a signed JWT, and protected routes require a valid token.

## Features
- Create users with securely hashed passwords (`POST /users`)
- Retrieve users (`GET /users`)
- Login that returns a JWT access token (`POST /login`)
- Protected route returning the current user (`GET /me`, requires a bearer token)
- Input validation with Pydantic (email format + password length)
- Parameterized SQL via psycopg2 to prevent injection
- Health check endpoint (`GET /health`)

## Tech Stack
- Python, FastAPI
- PostgreSQL (psycopg2)
- Passlib + bcrypt for password hashing
- PyJWT for token-based authentication
- Pydantic for request validation

## Endpoints
| Method | Path    | Auth   | Description                            |
|--------|---------|--------|----------------------------------------|
| GET    | /       | —      | Service status                         |
| GET    | /health | —      | Health check                           |
| GET    | /users  | —      | List users (id, name, email)           |
| POST   | /users  | —      | Create a user (name, email, password)  |
| POST   | /login  | —      | Verify credentials, return a JWT       |
| GET    | /me     | Bearer | Return the current authenticated user  |

## Configuration
Read from environment variables, with local defaults:

| Variable           | Default            | Purpose                         |
|--------------------|--------------------|---------------------------------|
| DB_NAME            | fast_apidb         | Database name                   |
| DB_USER            | adn                | Database user                   |
| DB_PASSWORD        | (empty)            | Database password               |
| DB_HOST            | localhost          | Database host                   |
| DB_PORT            | 5432               | Database port                   |
| JWT_SECRET_KEY     | dev-only-change-me | Secret used to sign tokens      |
| JWT_EXPIRE_MINUTES | 30                 | Access-token lifetime (minutes) |

Generate a real secret for anything beyond local dev:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
export JWT_SECRET_KEY=<paste-the-output>
```

## Database setup
```sql
CREATE DATABASE fast_apidb;
\c fast_apidb
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL
);
```

## How to run
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open the interactive docs at http://127.0.0.1:8000/docs

### Trying the auth flow in /docs
1. `POST /users` to create a user.
2. `POST /login` with the same email/password, then copy the `access_token` from the response.
3. Click **Authorize**, paste the token, and call `GET /me`.

## Tests
```bash
pip install -r requirements.txt
pytest
```

## Roadmap
- Integration tests for the API endpoints (against a test database)
- Alembic migrations (replacing manual schema changes)
- Dockerfile + docker-compose
- CI (GitHub Actions) and a live deployment
