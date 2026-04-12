from fastapi import FastAPI
from pydantic import BaseModel
from app.database import get_connection
from app.auth import hash_password, verify_password

app = FastAPI()

class User(BaseModel):
    name: str
    email: str
    password: str

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
    hashword = hash_password(user.password)
    cursor.execute(
        "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)", 
        (user.name, user.email, hashword)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return {"message": "User created"}

@app.post("/login")
def login(user: User):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT password FROM users WHERE email = %s",(user.email,) 
    )
    result = cursor.fetchone()

    if result is None:
        return {"error: User Not Found"}
    stored_passwords = result[0]
    if verify_password(user.password):
        return {"message : Login Successful"}
    else:
        return {"Error : Invalid Password"}