from pydantic import BaseModel, EmailStr, field_validator

from app.auth.models import UserRole


class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: UserRole

    @field_validator("username")
    @classmethod
    def username_length(cls, v: str) -> str:
        if not (3 <= len(v) <= 64):
            raise ValueError("username must be between 3 and 64 characters")
        return v

    @field_validator("password")
    @classmethod
    def password_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("password must be at least 8 characters")
        return v


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    username: str
    email: str
    role: UserRole
    country: str | None

    model_config = {"from_attributes": True}


class SetCountryRequest(BaseModel):
    country: str

    @field_validator("country")
    @classmethod
    def country_code_format(cls, v: str) -> str:
        if len(v) != 2 or not v.isalpha():
            raise ValueError("country must be a 2-letter ISO 3166-1 alpha-2 code")
        return v.upper()
