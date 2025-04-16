from fastapi import APIRouter, Depends, HTTPException
from ...dependencies.auth import get_current_user
from ...models.user import User

router = APIRouter()

@router.get("/me", response_model=dict)
def read_current_user(current_user: User = Depends(get_current_user)):
    """
    Get current user information.
    This is a placeholder endpoint that can be expanded later.
    """
    return {"user_id": current_user.id, "username": current_user.username}

@router.get("/users", response_model=list)
def read_users():
    """
    Get list of users.
    This is a placeholder endpoint that can be expanded later.
    """
    return [{"user_id": 1, "username": "testuser"}]
