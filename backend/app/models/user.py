from pydantic import BaseModel, EmailStr

class User(BaseModel):
    """User model for authentication and user management"""
    id: int
    username: str
    email: str
    is_active: bool = True
    # Add more fields as needed
