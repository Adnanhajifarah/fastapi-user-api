# FastAPI User API

## Overview
This is a RESTful backend API built using FastAPI and PostgreSQL that allows users to be created, stored, and retrieved from a database.

## Features
- Create users (POST)
- Retrieve users (GET)
- Input validation using Pydantic
- PostgreSQL database integration
- Structured JSON responses

## Tech Stack
- Python
- FastAPI
- PostgreSQL
- psycopg2

## Endpoints

### Create User
POST /users

### Get Users
GET /users

## How to Run

1. Clone the repository:
git clone https://github.com/Adnanhajifarah/fastapi-user-api.git

2. Navigate into the project:
cd fastapi-user-api

3. Create virtual environment:
python3 -m venv venv

4. Activate environment:
source venv/bin/activate

5. Install dependencies:
pip install -r requirements.txt

6. Run the server:
uvicorn app.main:app --reload

7. Open in browser:
http://127.0.0.1:8000/docs