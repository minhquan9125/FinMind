import hashlib
import hmac
import os
from urllib.parse import quote

import asyncpg
import jwt
from fastapi import APIRouter, BackgroundTasks, HTTPException, Response, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from starlette.concurrency import run_in_threadpool

from ...auth import repository
from ...auth.email_service import send_reset_email
from ...auth.rate_limiter import login_limiter
from ...auth.schemas import (
    ForgotPasswordRequest,
    GoogleLoginRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
)
from ...auth.service import (
    DUMMY_HASH,
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    hash_password,
    read_password_reset_token,
    verify_password,
)
from ...core.config import get_settings
from ...core.db import get_pool

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest):
    # Argon2 tốn tài nguyên; chạy trong threadpool để không chặn event loop.
    stored_hash = await run_in_threadpool(hash_password, payload.password)

    try:
        user = await repository.create_user(
            pool=get_pool(),
            email=payload.email,
            full_name=payload.full_name,
            password_hash=stored_hash,
            default_role_code="RESEARCHER",
        )
    except asyncpg.UniqueViolationError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email đã được sử dụng.",
        ) from None

    created_at_str = (
        user["created_at"].isoformat()
        if hasattr(user["created_at"], "isoformat")
        else str(user["created_at"])
    )

    return {
        "success": True,
        "data": {
            "user_id": str(user["user_id"]),
            "email": user["email"],
            "full_name": user["full_name"],
            "roles": user.get("roles", ["RESEARCHER"]),
            "created_at": created_at_str,
        },
    }


@router.post("/login")
async def login(payload: LoginRequest):
    settings = get_settings()

    # 1. Kiểm tra giới hạn thử liên tiếp (Account Lockout)
    is_locked, remaining_seconds = login_limiter.is_locked(payload.email)
    if is_locked:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Tài khoản tạm thời bị khóa do thử sai quá nhiều lần. Vui lòng thử lại sau {remaining_seconds} giây.",
            headers={"Retry-After": str(remaining_seconds)},
        )

    pool = get_pool()
    user = await repository.find_user_by_email(pool, payload.email)

    stored_hash = (
        user["password_hash"]
        if user is not None and user["password_hash"]
        else DUMMY_HASH
    )
    password_is_valid = await run_in_threadpool(
        verify_password, payload.password, stored_hash
    )

    # 2. Xử lý khi sai thông tin đăng nhập
    if (
        user is None
        or not password_is_valid
        or user["is_active"] is not True
        or not user["password_hash"]
    ):
        is_now_locked, remaining_or_lockout = login_limiter.record_failure(
            payload.email,
            max_attempts=settings.auth_max_failed_attempts,
            lockout_seconds=settings.auth_lockout_minutes * 60,
        )
        if is_now_locked:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Bạn đã thử đăng nhập sai quá {settings.auth_max_failed_attempts} lần liên tiếp. Tài khoản bị tạm khóa trong {settings.auth_lockout_minutes} phút.",
                headers={"Retry-After": str(remaining_or_lockout)},
            )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không đúng.",
        )

    # 3. Đăng nhập thành công -> Reset bộ đếm số lần sai
    login_limiter.record_success(payload.email)

    # 4. Lấy danh sách vai trò thực tế của người dùng
    user_roles = await repository.get_user_roles(pool, user["user_id"])

    # 5. Khởi tạo phiên và JWT token
    refresh_token, token_hash = create_refresh_token()
    await repository.create_session(
        pool, user["user_id"], token_hash, settings.refresh_token_days
    )
    await repository.record_login(pool, user["user_id"])

    return {
        "success": True,
        "data": {
            "access_token": create_access_token(
                user["user_id"], settings, user_roles
            ),
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": settings.access_token_minutes * 60,
            "user": {
                "user_id": str(user["user_id"]),
                "email": user["email"],
                "full_name": user["full_name"],
                "roles": user_roles,
            },
        },
    }

@router.post("/google")
async def login_with_google(payload: GoogleLoginRequest):
    settings = get_settings()
    google_client_id = os.getenv("GOOGLE_CLIENT_ID", "")

    try:
        # google-auth tự động gọi server Google kiểm tra chữ ký điện tử của ID Token
        id_info = id_token.verify_oauth2_token(
            payload.credential,
            google_requests.Request(),
            google_client_id if google_client_id else None,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token Google không hợp lệ hoặc đã hết hạn: {str(exc)}",
        )

    email = id_info.get("email")
    name = id_info.get("name", "")

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không lấy được địa chỉ email từ tài khoản Google.",
        )

    pool = get_pool()

    user = await repository.get_or_create_google_user(pool, email=email, full_name=name)

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản của bạn đã bị khóa.",
        )

    # 3. Lấy quyền và cấp JWT của FinMind
    user_roles = await repository.get_user_roles(pool, user["user_id"])
    refresh_token, token_hash = create_refresh_token()
    await repository.create_session(
        pool, user["user_id"], token_hash, settings.refresh_token_days
    )
    await repository.record_login(pool, user["user_id"])

    return {
        "success": True,
        "data": {
            "access_token": create_access_token(user["user_id"], settings, user_roles),
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": settings.access_token_minutes * 60,
            "user": {
                "user_id": str(user["user_id"]),
                "email": user["email"],
                "full_name": user["full_name"],
                "roles": user_roles,
            },
        },
    }

@router.post("/password/forgot", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
):
    message = "Nếu email đã đăng ký, bạn sẽ nhận được liên kết đặt lại mật khẩu."
    user = await repository.find_user_by_email(get_pool(), payload.email)

    if user and user["is_active"] and user["password_hash"]:
        settings = get_settings()
        token = create_password_reset_token(
            user["user_id"],
            user["password_hash"],
            settings,
        )
        reset_url = (
            f"{settings.frontend_url.rstrip('/')}/reset-password"
            f"#token={quote(token)}"
        )
        background_tasks.add_task(send_reset_email, user["email"], reset_url)

    return {"success": True, "message": message}


@router.post("/password/reset", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(payload: ResetPasswordRequest):
    invalid_message = "Liên kết không hợp lệ hoặc đã hết hạn."

    try:
        user_id, token_password_version = read_password_reset_token(
            payload.recovery_code,
            get_settings(),
        )
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail=invalid_message) from None

    pool = get_pool()
    user = await repository.find_user_by_id(pool, user_id)
    if not user or not user["is_active"] or not user["password_hash"]:
        raise HTTPException(status_code=400, detail=invalid_message)

    current_hash = user["password_hash"]
    current_version = hashlib.sha256(current_hash.encode()).hexdigest()
    if not hmac.compare_digest(current_version, token_password_version):
        raise HTTPException(status_code=400, detail=invalid_message)

    new_hash = await run_in_threadpool(hash_password, payload.new_password)
    changed = await repository.replace_password_if_current(
        pool, user_id, current_hash, new_hash
    )
    if not changed:
        raise HTTPException(status_code=400, detail=invalid_message)

    return Response(status_code=status.HTTP_204_NO_CONTENT)