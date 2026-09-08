"""
Auth service — registration, login, current user.

Registration flow:
  1. Validate email not already taken
  2. Hash the password
  3. Create the User row
  4. Create an Organization (from org_name in the request)
  5. Add the user as owner of that organization
  6. Issue a JWT access token
  7. Return token + user in a single response

All steps run in one database transaction (the session is committed
by the get_db() dependency after the route handler returns).
Flushing after each create() call makes the generated IDs available
within the same transaction without committing yet — so if step 5
fails, nothing is persisted.

Login flow:
  1. Look up user by email
  2. Verify bcrypt hash — use constant-time comparison (passlib handles this)
  3. Check is_active — soft-deleted users cannot log in
  4. Issue JWT

We raise HTTP 401 with a generic "Invalid credentials" message on both
wrong email and wrong password — we never hint which one is wrong.
"""

import re
import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.db.models.user import User
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, RegisterRequest, RegisterResponse, UserResponse, TokenResponse


def _slugify(text: str) -> str:
    """
    Convert a human-readable name to a URL-safe slug.
    "Acme Corp" → "acme-corp"
    "My   Project!!" → "my-project"
    """
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)   # remove non-alphanumeric
    slug = re.sub(r"[\s-]+", "-", slug)          # collapse whitespace/dashes
    slug = slug.strip("-")
    return slug or "org"


async def _make_unique_slug(
    base_slug: str,
    exists_fn,           # async callable: (slug) -> bool
) -> str:
    """
    Append a suffix until the slug is unique.
    "acme-corp" → "acme-corp-2" → "acme-corp-3" ...
    """
    slug = base_slug[:90]   # leave room for suffix
    if not await exists_fn(slug):
        return slug
    for i in range(2, 100):
        candidate = f"{slug}-{i}"
        if not await exists_fn(candidate):
            return candidate
    # Extremely unlikely fallback
    return f"{slug}-{uuid.uuid4().hex[:6]}"


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._users = UserRepository(db)
        self._orgs = OrganizationRepository(db)

    async def register(self, req: RegisterRequest) -> RegisterResponse:
        # ── 1. Email uniqueness ───────────────────────────────────────────────
        if await self._users.email_exists(req.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            )

        # ── 2. Create user ────────────────────────────────────────────────────
        user = await self._users.create(
            email=req.email,
            full_name=req.full_name,
            password_hash=hash_password(req.password),
        )

        # ── 3. Create organization ────────────────────────────────────────────
        base_slug = _slugify(req.org_name)
        org_slug = await _make_unique_slug(base_slug, self._orgs.slug_exists)
        org = await self._orgs.create(name=req.org_name, slug=org_slug)

        # ── 4. Make user the owner ────────────────────────────────────────────
        await self._orgs.add_member(
            org_id=org.id,
            user_id=user.id,
            role="owner",
        )

        # ── 5. Issue token ────────────────────────────────────────────────────
        token = create_access_token(str(user.id))

        return RegisterResponse(
            user=UserResponse.model_validate(user),
            access_token=token,
            token_type="bearer",
        )

    async def login(self, req: LoginRequest) -> TokenResponse:
        # ── 1. Look up user ───────────────────────────────────────────────────
        user = await self._users.get_by_email(req.email)

        # ── 2. Verify — same error for wrong email and wrong password ─────────
        invalid = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        if user is None or not verify_password(req.password, user.password_hash):
            raise invalid

        # ── 3. Active check ───────────────────────────────────────────────────
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is disabled. Contact support.",
            )

        # ── 4. Issue token ────────────────────────────────────────────────────
        token = create_access_token(str(user.id))
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user=UserResponse.model_validate(user),
        )

    async def get_current_user(self, user_id: str) -> User:
        """
        Load the full User object from the database.
        Called by the get_current_user FastAPI dependency.
        """
        try:
            uid = uuid.UUID(user_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token subject.",
            )

        user = await self._users.get_by_id(uid)
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or account disabled.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user
