# FastAPI User API

A RESTful backend API built with FastAPI and PostgreSQL for user registration,
retrieval, and authentication. Passwords are hashed with bcrypt before storage,
and login verifies submitted credentials against the stored hash.

## Features
- Create users with securely hashed passwords (`POST /users`)
- Retrieve users (`GET /users`)
- User login with credential verification (`POST /login`)
- Input validation with Pydantic (email format + password length)
- Parameterized SQL via psycopg2 to prevent injection
- Health check endpoint (`GET /health`)

## Tech Stack
- Python, FastAPI
- PostgreSQL (psycopg2)
- Passlib + bcrypt for password hashing
- Pydantic for request validation

## Endpoints
| Method | Path     | Description                            |
|--------|----------|----------------------------------------|
| GET    | /        | Service status                         |
| GET    | /health  | Health check                           |
| GET    | /users   | List users (id, name, email)           |
| POST   | /users   | Create a user (name, email, password)  |
| POST   | /login   | Verify credentials and log a user in   |

## Configuration
The database connection reads from environment variables, with local defaults:

| Variable    | Default    |
|-------------|------------|
| DB_NAME     | fast_apidb |
| DB_USER     | adn        |
| DB_PASSWORD | (empty)    |
| DB_HOST     | localhost  |
| DB_PORT     | 5432       |

## Database setup
Create the database and `users` table before running:

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

Then open the interactive docs at http://127.0.0.1:8000/docs

## Roadmap
- JWT-based authentication with protected routes
- Automated tests (pytest) against a dedicated test database
- Alembic migrations (replacing manual schema changes)
- Dockerfile + docker-compose
- CI (GitHub Actions) and a live deployment
