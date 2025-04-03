from dotenv import load_dotenv
from fastapi import APIRouter, Depends, Form, Request, status, HTTPException
from sqlalchemy import select, insert
from typing import Annotated
from app.rate_limiter import limiter
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from datetime import datetime, timedelta, timezone
import jwt

from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.security import OAuth2PasswordBearer

import os

from app.models.users import Users
from app.schemas import CreateUser
from app.database.db_depends import get_db
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm


load_dotenv()

SECRET_KEY = os.getenv('SECRET_KEY')
# Важно: tokenUrl должен соответствовать реальному пути к эндпоинту токена
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

ALGORITHM = 'HS256'

# Измените префикс роутера на '/auth'
router = APIRouter(prefix='/token', tags=['authentication'])
bcrypt_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

async def authenticate_user(db: AsyncSession, email: str, password: str):
    user = await db.scalar(select(Users).where(Users.email == email))
    if not user or not bcrypt_context.verify(password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

def create_access_token(data: dict, expires_delta: timedelta = timedelta(minutes=30)):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        user_id = payload.get("id")
        if email is None or user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        return {"email": email, "id": user_id}
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

@router.post("/")
@limiter.limit("5/minute")
async def login_for_access_token(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    # Используем username как email
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    
    access_token = create_access_token(
        data={"sub": user.email, "id": user.id}
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me")
@limiter.limit("5/minute")
async def read_users_me(request: Request, current_user: Annotated[dict, Depends(get_current_user)]):
    return current_user

@router.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"error": "Too Many Requests"}
    )