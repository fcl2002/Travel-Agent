"""Authenticate users and manage rotating, revocable login sessions."""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import secrets
from uuid import uuid4

from app.core.exceptions import AuthenticationError
from app.core.security import hash_password, verify_password
from app.core.tokens import JWTTokenService
from app.models.auth_session import AuthSession, AuthTokens
from app.models.user import User
from app.repositories.auth_session_repository import AuthSessionRepository
from app.repositories.user_repository import UserRepository

_DUMMY_HASH = hash_password(secrets.token_urlsafe(32))


def token_hash(token: str) -> str:
    # Refresh JWTs have high-entropy signatures and random IDs, unlike passwords.
    return hashlib.sha256(token.encode()).hexdigest()


class AuthService:
    def __init__(self, users: UserRepository, sessions: AuthSessionRepository,
                 token_service: JWTTokenService, refresh_days: int = 7):
        self.users, self.sessions, self.token_service = users, sessions, token_service
        self.refresh_days = refresh_days

    def _issue_tokens(self, session: AuthSession) -> AuthTokens:
        return AuthTokens(
            access_token=self.token_service.create_access_token(session.user_id, session.id),
            refresh_token=self.token_service.create_refresh_token(session.user_id, session.id, session.expires_at),
            refresh_expires_at=session.expires_at,
        )

    async def login(self, *, email: str, password: str) -> AuthTokens:
        user = await self.users.get_by_email(email)
        valid = await asyncio.to_thread(
            verify_password, password, user.password_hash if user else _DUMMY_HASH,
        )
        if user is None or not valid:
            raise AuthenticationError()
        if not user.is_active:
            # Reactivation must not restore access through pre-deactivation tokens.
            await self.sessions.revoke_for_user(user.id)
            user = await self.users.update(replace(user, is_active=True))
        now = datetime.now(UTC)
        session = AuthSession(id=uuid4(), user_id=user.id, refresh_token_hash="",
                              created_at=now, expires_at=now + timedelta(days=self.refresh_days))
        tokens = self._issue_tokens(session)
        await self.sessions.add(replace(session, refresh_token_hash=token_hash(tokens.refresh_token)))
        return tokens

    async def refresh(self, token: str) -> AuthTokens | None:
        """Return None when this call revoked the session.

        Do not raise in that case: an exception rolls back the transaction and undoes the revocation.
        """
        identity = self.token_service.decode_refresh_token(token)
        session = await self.sessions.get_by_id(identity.session_id, for_update=True)
        now = datetime.now(UTC)
        if session is None or session.user_id != identity.user_id or not session.is_valid_at(now):
            raise AuthenticationError()
        if not hmac.compare_digest(session.refresh_token_hash, token_hash(token)):
            # A signed, superseded refresh token proves reuse of this session.
            # Return normally so the outer transaction commits this revocation.
            await self.sessions.save(replace(session, revoked_at=now))
            return None
        user = await self.users.get_by_id(identity.user_id)
        if user is None or not user.is_active:
            await self.sessions.save(replace(session, revoked_at=now))
            return None
        tokens = self._issue_tokens(session)
        await self.sessions.save(replace(session, refresh_token_hash=token_hash(tokens.refresh_token)))
        return tokens

    async def logout(self, token: str | None) -> None:
        if not token:
            return
        try:
            identity = self.token_service.decode_refresh_token(token)
        except AuthenticationError:
            return
        session = await self.sessions.get_by_id(identity.session_id, for_update=True)
        if session is not None and session.user_id == identity.user_id and session.revoked_at is None:
            await self.sessions.save(replace(session, revoked_at=datetime.now(UTC)))

    async def get_current_user(self, token: str) -> User:
        identity = self.token_service.decode_access_token(token)
        session = await self.sessions.get_by_id(identity.session_id)
        if session is None or session.user_id != identity.user_id or not session.is_valid_at(datetime.now(UTC)):
            raise AuthenticationError()
        user = await self.users.get_by_id(identity.user_id)
        if user is None or not user.is_active:
            raise AuthenticationError()
        return user
