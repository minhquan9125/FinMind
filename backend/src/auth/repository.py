from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import asyncpg


DEFAULT_ROLE_CODE = "RESEARCHER"
DEFAULT_ROLE_DESC = "Nha nghien cuu "


async def get_or_create_role(
    conn: asyncpg.Connection,
    role_code: str = DEFAULT_ROLE_CODE,
    description: str = DEFAULT_ROLE_DESC,
) -> asyncpg.Record:
    """Retrieve an existing role or create it if absent in public.roles."""
    role = await conn.fetchrow(
        "SELECT role_id, role_code, description FROM public.roles WHERE role_code = $1",
        role_code,
    )
    if role is None:
        role = await conn.fetchrow(
            """
            INSERT INTO public.roles (role_id, role_code, description)
            VALUES ($1, $2, $3)
            RETURNING role_id, role_code, description
            """,
            uuid4(),
            role_code,
            description,
        )
    return role


async def create_user(
    pool: asyncpg.Pool,
    email: str,
    full_name: str,
    password_hash: str,
    default_role_code: str = DEFAULT_ROLE_CODE,
) -> dict:
    """Create a new user in public.users and automatically assign the default role in public.user_roles."""
    new_user_id = uuid4()
    async with pool.acquire() as conn:
        async with conn.transaction():
            user_row = await conn.fetchrow(
                """
                INSERT INTO public.users
                    (user_id, email, full_name, password_hash,
                     is_active, created_at, updated_at)
                VALUES ($1, $2, $3, $4, true, now(), now())
                RETURNING user_id, email, full_name, is_active, created_at
                """,
                new_user_id,
                email,
                full_name,
                password_hash,
            )

            # Ensure default role exists and assign it
            role = await get_or_create_role(conn, default_role_code)
            await conn.execute(
                """
                INSERT INTO public.user_roles (user_id, role_id)
                VALUES ($1, $2)
                ON CONFLICT DO NOTHING
                """,
                new_user_id,
                role["role_id"],
            )

    return {
        "user_id": user_row["user_id"],
        "email": user_row["email"],
        "full_name": user_row["full_name"],
        "is_active": user_row["is_active"],
        "created_at": user_row["created_at"],
        "roles": [default_role_code],
    }


async def get_user_roles(pool: asyncpg.Pool, user_id: UUID) -> list[str]:
    """Fetch assigned role codes for a user."""
    rows = await pool.fetch(
        """
        SELECT r.role_code
        FROM public.user_roles ur
        JOIN public.roles r ON ur.role_id = r.role_id
        WHERE ur.user_id = $1
        """,
        user_id,
    )
    roles = [r["role_code"] for r in rows if r["role_code"]]
    return roles or [DEFAULT_ROLE_CODE]


async def find_user_by_email(
    pool: asyncpg.Pool,
    email: str,
) -> asyncpg.Record | None:
    return await pool.fetchrow(
        """
        SELECT user_id, email, full_name, password_hash, is_active
        FROM public.users
        WHERE lower(email) = $1
        """,
        email.lower(),
    )


async def create_session(
    pool: asyncpg.Pool,
    user_id: UUID,
    token_hash: str,
    refresh_token_days: int,
) -> None:
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=refresh_token_days
    )
    await pool.execute(
        """
        INSERT INTO public.sessions
            (session_id, user_id, token_hash, issued_at, expires_at)
        VALUES ($1, $2, $3, now(), $4)
        """,
        uuid4(),
        user_id,
        token_hash,
        expires_at,
    )


async def record_login(pool: asyncpg.Pool, user_id: UUID) -> None:
    await pool.execute(
        """
        UPDATE public.users
        SET last_login_at = now()
        WHERE user_id = $1
        """,
        user_id,
    )

async def get_or_create_google_user(
    pool: asyncpg.Pool,
    email: str,
    full_name: str,
    default_role_code: str = DEFAULT_ROLE_CODE,
) -> dict:
    """Tìm user theo email; nếu chưa có thì tạo mới (không cần password) và cấp quyền mặc định."""
    async with pool.acquire() as conn:
        async with conn.transaction():
            user = await conn.fetchrow(
                "SELECT user_id, email, full_name, is_active FROM public.users WHERE email = $1",
                email,
            )
            if user is None:
                new_id = uuid4()
                # Tạo user mới, password_hash để None vì đăng nhập qua Google
                user = await conn.fetchrow(
                    """
                    INSERT INTO public.users (user_id, email, full_name, password_hash, is_active, created_at, updated_at)
                    VALUES ($1, $2, $3, NULL, true, now(), now())
                    RETURNING user_id, email, full_name, is_active
                    """,
                    new_id,
                    email,
                    full_name or email.split("@")[0],
                )
                # Gán quyền RESEARCHER mặc định
                role = await get_or_create_role(conn, default_role_code)
                await conn.execute(
                    """
                    INSERT INTO public.user_roles (user_id, role_id)
                    VALUES ($1, $2)
                    ON CONFLICT DO NOTHING
                    """,
                    new_id,
                    role["role_id"],
                )
            return dict(user)
            