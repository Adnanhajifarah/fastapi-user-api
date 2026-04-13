from pydantic import BaseModel, EmailStr, constr

class User(BaseModel):
    name: str
    email: EmailStr
    password: constr(min_length=6, max_length=72)