import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from database import get_db
from models import User
from email_utils import send_password_reset_email

router = APIRouter(prefix="/auth", tags=["Auth"])

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 12
PASSWORD_RESET_EXPIRE_MINUTES = 30

if not SECRET_KEY or SECRET_KEY == "CHANGE_THIS_SECRET":
    raise RuntimeError("SECRET_KEY environment variable is missing or insecure.")

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
bearer_scheme = HTTPBearer()


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str
    needs_onboarding: bool


class UserOut(BaseModel):
    id: int
    email: EmailStr
    username: str

    class Config:
        from_attributes = True


class RegisterResponse(BaseModel):
    message: str
    user: UserOut


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    reset_token: str
    new_password: str


class OnboardingCompleteResponse(BaseModel):
    message: str
    onboarding_completed: bool


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_minutes: Optional[int] = None) -> str:
    to_encode = data.copy()
    if expires_minutes is None:
        expires_minutes = ACCESS_TOKEN_EXPIRE_HOURS * 60
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    email = normalize_email(email)
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == int(user_id)).first()


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    user = get_user_by_email(db, email)
    if not user or not user.password_hash:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        user_id = payload.get("user_id")
        if user_id is not None:
            user = get_user_by_id(db, int(user_id))
            if user:
                return user

        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token payload")

        email = normalize_email(email)

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = get_user_by_email(db, email=email)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


def verify_password_reset_token(token: str, db: Session) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        token_type = payload.get("type")
        email = payload.get("sub")

        if token_type != "password_reset" or not email:
            raise HTTPException(status_code=400, detail="Invalid or expired reset token")

        user = get_user_by_email(db, email)
        if not user:
            raise HTTPException(status_code=400, detail="Invalid or expired reset token")

        return user

    except JWTError as e:
        print("JWT ERROR while verifying reset token:", e)
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")


def get_onboarding_completed(user: User) -> bool:
    return bool(getattr(user, "onboarding_completed", False))


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    email = normalize_email(payload.email)

    if get_user_by_email(db, email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")

    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already in use")

    user = User(
        email=email,
        username=payload.username,
        password_hash=hash_password(payload.password),
    )

    try:
        user.onboarding_completed = False
    except Exception:
        setattr(user, "onboarding_completed", False)

    db.add(user)
    db.commit()
    db.refresh(user)

    return RegisterResponse(message="User created successfully.", user=user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    email = normalize_email(payload.email)
    user = authenticate_user(db, email, payload.password)

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    token = create_access_token({"sub": user.email, "user_id": user.id})

    onboarding_completed = get_onboarding_completed(user)
    needs_onboarding = not onboarding_completed

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_id=user.id,
        username=user.username,
        needs_onboarding=needs_onboarding,
    )


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/onboarding/complete", response_model=OnboardingCompleteResponse)
def complete_onboarding(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not get_onboarding_completed(current_user):
        try:
            current_user.onboarding_completed = True
        except Exception:
            setattr(current_user, "onboarding_completed", True)

        db.add(current_user)
        db.commit()
        db.refresh(current_user)

    return OnboardingCompleteResponse(
        message="Onboarding marked as completed.",
        onboarding_completed=True,
    )


@router.post("/request-password-reset")
def request_password_reset(payload: PasswordResetRequest, db: Session = Depends(get_db)):
    email = normalize_email(payload.email)
    user = get_user_by_email(db, email)

    if not user:
        return {"message": "If this email exists, a reset email has been sent."}

    reset_token = create_access_token(
        {"sub": user.email, "type": "password_reset"},
        expires_minutes=PASSWORD_RESET_EXPIRE_MINUTES,
    )

    try:
        send_password_reset_email(user.email, reset_token)
        return {"message": "Password reset email sent."}
    except Exception as e:
        print("EMAIL ERROR:", e)
        return {
            "message": "Failed to send email. (DEV) Returning reset token.",
            "reset_token": reset_token,
        }


@router.post("/reset-password")
def reset_password(payload: PasswordResetConfirm, db: Session = Depends(get_db)):
    user = verify_password_reset_token(payload.reset_token, db)
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return {"message": "Password updated successfully"}
