"""
Auth: password hashing, JWT create/verify, get_current_user dependency.
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext

import config
from app.repositories.protocols import UserRepository
from app.deps import get_user_repository
from app.core.settings import get_settings

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return pwd_ctx.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)


def create_access_token(subject: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=config.JWT_EXPIRE_MINUTES)
    to_encode = {"sub": subject, "exp": expire}
    return jwt.encode(to_encode, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def decode_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
        sub = payload.get("sub")
        return str(sub) if sub else None
    except JWTError:
        return None


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    user_repo: UserRepository = Depends(get_user_repository),
) -> dict:
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = decode_token(credentials.credentials)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = user_repo.get_by_id(int(user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    email = user["email"]
    admin_emails = [e.lower() for e in get_settings().admin_emails]
    is_admin = email.lower() in admin_emails if admin_emails else False
    return {"id": user["id"], "email": email, "name": user["name"], "is_admin": is_admin}


async def get_current_admin_user(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Require authenticated user with admin role (email in ADMIN_EMAILS)."""
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user
