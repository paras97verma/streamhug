"""Authentication domain models and API schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class UserProfile(BaseModel):
    user_id: str
    email: str
    name: str
    is_verified: bool
    role: Literal["admin", "user"] = "user"
    created_at: int


class SignupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class SigninRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class VerifyAccountRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    code: str = Field(min_length=6, max_length=12)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=32)


class ResendVerificationRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class AuthTokens(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class SignupResponse(BaseModel):
    user: UserProfile
    verification_required: bool = True
    verification_debug_code: str | None = None


class SigninResponse(BaseModel):
    user: UserProfile
    tokens: AuthTokens


class VerifyAccountResponse(BaseModel):
    user: UserProfile
    tokens: AuthTokens


class UserRecord(BaseModel):
    user_id: str
    email: str
    name: str
    password_hash: str
    is_verified: bool = False
    role: Literal["admin", "user"] = "user"
    created_at: int
    verification_code_hash: str = ""
    verification_expires_at: int = 0
    active_refresh_tokens: dict[str, int] = Field(default_factory=dict)
