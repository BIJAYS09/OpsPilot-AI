"""
JWT auth helpers.
- create_access_token / create_refresh_token
- verify_token
- get_current_user  (FastAPI dependency)
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from core.config import get_settings

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

# ── Fake user store (replace with DB table in production) ─────────────────────
FAKE_USERS = {
    "operator@plant.com": {
        "email": "operator@plant.com",
        "full_name": "Plant Operator",
        "role": "operator",
        "hashed_password": pwd_context.hash("operator123"),
    },
    "engineer@plant.com": {
        "email": "engineer@plant.com",
        "full_name": "Lead Engineer",
        "role": "engineer",
        "hashed_password": pwd_context.hash("engineer123"),
    },
    "admin@plant.com": {
        "email": "admin@plant.com",
        "full_name": "System Admin",
        "role": "admin",
        "hashed_password": pwd_context.hash("admin123"),
    },
}


# ── Password helpers ──────────────────────────────────────────────────────────

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def authenticate_user(email: str, password: str) -> Optional[dict]:
    user = FAKE_USERS.get(email)
    if not user or not verify_password(password, user["hashed_password"]):
        return None
    return user


# ── Token creation ────────────────────────────────────────────────────────────

def create_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload["type"] = "access"
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    payload["type"] = "refresh"
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


# ── Token verification ────────────────────────────────────────────────────────

def verify_token(token: str, expected_type: str = "access") -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY,
                             algorithms=[settings.ALGORITHM])
        if payload.get("type") != expected_type:
            raise JWTError("Wrong token type")
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalid or expired",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── FastAPI dependency: current user ──────────────────────────────────────────

async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    payload = verify_token(token, expected_type="access")
    email   = payload.get("sub")
    user    = FAKE_USERS.get(email)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="User not found")
    return user


def require_role(*roles: str):
    """Factory: returns a dependency that enforces a role list."""
    async def _check(user: dict = Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=f"Role '{user['role']}' not permitted here.")
        return user
    return _check
