"""Server-side authentication and role checks for protected API routes."""

from dataclasses import dataclass
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import repository
from .service import read_access_token
from ..core.config import get_settings
from ..core.db import get_pool


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    roles: frozenset[str]


bearer = HTTPBearer(auto_error=False)


async def current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> Principal:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        user_id = read_access_token(credentials.credentials, get_settings())
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token") from None
    pool = get_pool()
    user = await repository.find_user_by_id(pool, user_id)
    if user is None or user["is_active"] is not True:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive account")
    # Read current grants from the server, so a revoked role takes effect before JWT expiry.
    roles = frozenset(await repository.get_user_roles(pool, user_id))
    return Principal(user_id, roles)


def require_roles(*allowed: str):
    async def check(principal: Principal = Depends(current_principal)) -> Principal:
        if not principal.roles.intersection(allowed):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return principal

    return check


READ_ROLES = ("RESEARCHER", "FINANCIAL_ANALYST", "DATA_ENGINEER", "EVALUATOR", "ADMINISTRATOR")
WRITE_ROLES = ("DATA_ENGINEER", "ADMINISTRATOR")
