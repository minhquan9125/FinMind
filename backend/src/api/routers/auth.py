import asyncpg
from fastapi import APIRouter, HTTPException, status
from starlette.concurrency import run_in_threadpool

from ...auth import repository
from ...auth.rate_limiter import login_limiter
from ...auth.schemas import LoginRequest, RegisterRequest
from ...auth.service import (
    DUMMY_HASH,
    create_access_token,
    create_refresh_token,
    hash_password,
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