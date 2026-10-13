# FastAPI User API

A RESTful backend API built with FastAPI and PostgreSQL for user registration,
retrieval, and JWT-based authentication. Passwords are hashed with bcrypt before
storage; login issues a signed JWT, and protected routes require a valid token.

## Features
- Create users with securely hashed passwords (`POST /users`)
- List users, paginated and token-protected (`GET /users`)
- Login that returns a JWT access token (`POST /login`)
- Protected route returning the current user (`GET /me`, requires a bearer token)
- Login failures reveal nothing about which emails are registered: identical
  response and equalized response time whether the account exists or not
- Versioned schema with Alembic migrations, including pgvector for the
  recommender work in progress
- TMDB catalog ingestion as a re-runnable CLI script (`python -m app.ingest`)
- Pooled database connections, released on every path including errors
- Input validation with Pydantic (email format + password length)
- Parameterized SQL via psycopg2 to prevent injection
- Health check endpoint (`GET /health`)

## Tech Stack
- Python, FastAPI
- PostgreSQL (psycopg2, with a threaded connection pool)
- Alembic for schema migrations; pgvector for embeddings
- Passlib + bcrypt for password hashing
- PyJWT for token-based authentication
- Pydantic for request validation

## Endpoints
| Method | Path    | Auth   | Description                            |
|--------|---------|--------|----------------------------------------|
| GET    | /       | —      | Service status                         |
| GET    | /health | —      | Health check                           |
| GET    | /users  | Bearer | List users, paginated (`limit`, `offset`) |
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
| APP_ENV            | development        | Set to `production` to require a real `JWT_SECRET_KEY` |
| DB_POOL_MIN        | 1                  | Minimum pooled connections      |
| DB_POOL_MAX        | 10                 | Maximum pooled connections      |

With `APP_ENV=production` the app refuses to start unless `JWT_SECRET_KEY` is
set, rather than silently signing tokens with the public development key.

Generate a real secret for anything beyond local dev:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
export JWT_SECRET_KEY=<paste-the-output>
```

## Database setup

Create the database, then let Alembic build the schema. The `movies` table uses
pgvector, so the extension must be available to the server.

```bash
createdb fast_apidb
alembic upgrade head
```

`alembic upgrade head` creates `users`, `movies` and `favorites`, and enables the
pgvector extension. The schema lives in `alembic/versions/` rather than in
hand-run SQL, so a fresh clone reproduces it exactly.

Useful commands:

```bash
alembic current    # which revision this database is on
alembic history    # the full chain of revisions
alembic downgrade -1   # undo the most recent revision
```

## Loading the film catalog

Ingestion is a command-line script, not an endpoint - it makes hundreds of
outbound requests and takes minutes. Get a free TMDB key at
<https://www.themoviedb.org/settings/api>, then:

```bash
export TMDB_API_KEY=your-key-here
python -m app.ingest --pages 100        # ~2,000 films, 20 per page
python -m app.ingest --pages 2 --dry-run  # fetch and parse, write nothing
```

Re-running is safe. Films are matched on their TMDB id, so a second run updates
existing rows rather than duplicating them. If a film's title or overview has
changed, its stored embedding is cleared so the backfill recomputes it; films
whose text is unchanged keep theirs.

See `.env.example` for every environment variable the project reads.

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
- Embedding backfill for ingested films
- `POST /recommend`: vector retrieval plus LLM ranking, with a keyword-search baseline
- Integration tests for the API endpoints (against a test database)
- Dockerfile + docker-compose
- CI (GitHub Actions) and a live deployment
