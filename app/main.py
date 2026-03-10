from fastapi import FastAPI
from pydantic import BaseModel
from app.database import get_connection

app = FastAPI()

class User(BaseModel):
    name: str
    email: str

@app.get("/")
def root():
    return {"message": "Backend API is running"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.get("/users")
def get_users():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id,name,email FROM users")
    rows = cursor.fetchall()
    users = []
    for row in rows:
        user = {
            "id": row[0],
            "name": row[1],
            "email": row[2]
        }
        users.append(user)
    cursor.close()
    conn.close()

    return {"users": users}


@app.post("/users")
def create_user(user: User):
    conn = get_connection()
    cursor = conn.cursor() 
    cursor.execute(
        "INSERT INTO users (name, email) VALUES (%s, %s)", 
        (user.name, user.email)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return {"message": "User created"}