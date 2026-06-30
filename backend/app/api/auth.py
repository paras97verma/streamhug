"""Authentication API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from app.core.dependencies import AuthServiceDep, CurrentUserDep
from app.models.auth import (
    RefreshTokenRequest,
    ResendVerificationRequest,
    SigninRequest,
    SigninResponse,
    SignupRequest,
    SignupResponse,
    VerifyAccountRequest,
    VerifyAccountResponse,
)
from app.services.auth import AuthError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=SignupResponse, summary="Create a new account")
async def signup(
    payload: SignupRequest,
    auth_service: AuthServiceDep,
) -> SignupResponse:
    """Create an account and generate a verification code."""
    try:
        return await auth_service.signup(payload)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post(
    "/resend-verification",
    response_model=SignupResponse,
    summary="Regenerate account verification code",
)
async def resend_verification(
    payload: ResendVerificationRequest,
    auth_service: AuthServiceDep,
) -> SignupResponse:
    try:
        return await auth_service.resend_verification(payload.email)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post(
    "/verify",
    response_model=VerifyAccountResponse,
    summary="Verify account and issue tokens",
)
async def verify_account(
    payload: VerifyAccountRequest,
    auth_service: AuthServiceDep,
) -> VerifyAccountResponse:
    try:
        return await auth_service.verify_account(payload.email, payload.code)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/signin", response_model=SigninResponse, summary="Sign in to an account")
async def signin(
    payload: SigninRequest,
    auth_service: AuthServiceDep,
) -> SigninResponse:
    try:
        user, tokens = await auth_service.signin(payload)
        return SigninResponse(user=user, tokens=tokens)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post(
    "/refresh",
    response_model=SigninResponse,
    summary="Rotate refresh token and issue a new access token",
)
async def refresh_token(
    payload: RefreshTokenRequest,
    auth_service: AuthServiceDep,
) -> SigninResponse:
    try:
        user, tokens = await auth_service.refresh(payload.refresh_token)
        return SigninResponse(user=user, tokens=tokens)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/me", summary="Return the current authenticated user")
async def get_current_user_profile(current_user: CurrentUserDep) -> dict[str, object]:
    return {"user": current_user}
