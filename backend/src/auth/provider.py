from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

import asyncpg

from . import repository
from ..core.config import Settings


class AuthProvider(ABC):
    """Abstract authentication provider contract."""

    @abstractmethod
    async def register_user(
        self,
        pool: asyncpg.Pool,
        email: str,
        full_name: str,
        password_hash: str,
    ) -> dict[str, Any]:
        """Register a new user account."""
        pass

    @abstractmethod
    async def authenticate_user(
        self,
        pool: asyncpg.Pool,
        email: str,
    ) -> asyncpg.Record | None:
        """Find an existing user record for authentication."""
        pass


class LocalDatabaseAuthProvider(AuthProvider):
    """Local provider using PostgreSQL database with Argon2 password hashing and internal sessions."""

    async def register_user(
        self,
        pool: asyncpg.Pool,
        email: str,
        full_name: str,
        password_hash: str,
    ) -> dict[str, Any]:
        return await repository.create_user(
            pool=pool,
            email=email,
            full_name=full_name,
            password_hash=password_hash,
            default_role_code="RESEARCHER",
        )

    async def authenticate_user(
        self,
        pool: asyncpg.Pool,
        email: str,
    ) -> asyncpg.Record | None:
        return await repository.find_user_by_email(pool, email)


# Default provider instance
default_auth_provider = LocalDatabaseAuthProvider()
