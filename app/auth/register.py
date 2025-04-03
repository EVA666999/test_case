
from fastapi import APIRouter, Depends, Request,status
from sqlalchemy import select, insert
from typing import Annotated
from app.rate_limiter import limiter




from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext


from app.models.users import Users
from app.schemas import CreateUser
from app.database.db_depends import get_db





router = APIRouter(prefix='/register', tags=['authentication'])
bcrypt_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

@limiter.limit("3/minute")
@router.post('/')
async def create_user(
    request: Request,
    db: Annotated[AsyncSession, 
        Depends(get_db)], create_user: CreateUser):
    await db.execute(insert(Users).values(
        email=create_user.email,
        password=bcrypt_context.hash(create_user.password),
    ))
    await db.commit()
    return {
        'status_code': status.HTTP_201_CREATED,
        'transaction': 'Successful'
    }