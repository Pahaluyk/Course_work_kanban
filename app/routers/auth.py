from fastapi import APIRouter, Depends, HTTPException, Response, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import User
from app.schemas import UserRegister, UserLogin, Token, UserOut
from app.services.auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="templates")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request})


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("auth/register.html", {"request": request})


@router.post("/register")
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    # Check username/email uniqueness
    result = await db.execute(select(User).where(
        (User.username == data.username) | (User.email == data.email)
    ))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Пользователь с таким именем или email уже существует")

    if data.role not in ("manager", "developer", "observer"):
        raise HTTPException(status_code=400, detail="Недопустимая роль")

    user = User(
        username=data.username,
        email=data.email,
        password_hash=hash_password(data.password),
        role=data.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {"message": "Регистрация успешна", "user_id": str(user.id)}


@router.post("/login")
async def login(data: UserLogin, response: Response, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == data.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")

    token = create_access_token({"sub": str(user.id)})
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=60 * 480,
        samesite="lax",
    )
    return Token(
        access_token=token,
        token_type="bearer",
        user=UserOut.model_validate(user),
    )


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "Выход выполнен"}


@router.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    return UserOut.model_validate(current_user)