from fastapi import APIRouter
from app.database import get_connection
from app.auth import hash_password, verify_password
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


@router.post("/users")
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

@router.post("/login")
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
    if verify_password(user.password,stored_passwords):
        return {"message : Login Successful"}
    else:
        return {"Error : Invalid Password"}