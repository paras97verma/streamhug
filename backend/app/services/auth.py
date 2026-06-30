"""SQLite-backed authentication service with JWT-style bearer tokens."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import secrets
import sqlite3
import time
import uuid

import jwt
from passlib.context import CryptContext

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.models.auth import (
    AuthTokens,
    SigninRequest,
    SignupRequest,
    SignupResponse,
    UserProfile,
    UserRecord,
    VerifyAccountResponse,
)

logger = get_logger("auth")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthError(Exception):
    """Domain exception for auth flow errors."""

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class AuthService:
    """Manages account lifecycle, verification, and token issuance."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._db_path = settings.auth_db_path
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Create the auth schema on startup.

        A dedicated SQLite store improves correctness for signup, verification,
        and refresh-token rotation because updates are transactional instead of
        full-file rewrites.
        """
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(self._initialize_sync)

    async def close(self) -> None:
        return None

    async def signup(self, payload: SignupRequest) -> SignupResponse:
        self._ensure_enabled()
        async with self._lock:
            user = await self._get_user(payload.email)
            if user is not None and user.is_verified:
                raise AuthError("An account with this email already exists", status_code=409)

            now = int(time.time())
            role = await self._determine_role(payload.email)
            updated = UserRecord(
                user_id=user.user_id if user is not None else uuid.uuid4().hex,
                email=payload.email,
                name=payload.name,
                password_hash=self._hash_password(payload.password),
                is_verified=True,
                role=role,
                created_at=user.created_at if user is not None else now,
                verification_code_hash="",
                verification_expires_at=0,
                active_refresh_tokens={},
            )
            await self._upsert_user(updated)
            await self._delete_refresh_tokens_for_user(updated.user_id)
            return SignupResponse(
                user=self._to_profile(updated),
                verification_required=False,
                verification_debug_code=None,
            )

    async def resend_verification(self, email: str) -> SignupResponse:
        self._ensure_enabled()
        async with self._lock:
            user = await self._get_user(email)
            if user is None:
                raise AuthError("Account not found", status_code=404)
            if user.is_verified:
                raise AuthError("Account is already verified", status_code=409)

            verification_code = self._generate_code()
            user.verification_code_hash = self._hash_code(verification_code)
            user.verification_expires_at = int(time.time()) + self._settings.auth_verification_code_ttl_seconds
            await self._upsert_user(user)
            self._deliver_verification_code(user.email, verification_code)
            return SignupResponse(
                user=self._to_profile(user),
                verification_required=True,
                verification_debug_code=self._maybe_expose_code(verification_code),
            )

    async def verify_account(self, email: str, code: str) -> VerifyAccountResponse:
        self._ensure_enabled()
        async with self._lock:
            user = await self._get_user(email)
            if user is None:
                raise AuthError("Account not found", status_code=404)

            if not user.is_verified:
                if int(time.time()) > user.verification_expires_at:
                    raise AuthError("Verification code expired", status_code=401)
                if not hmac.compare_digest(user.verification_code_hash, self._hash_code(code)):
                    raise AuthError("Invalid verification code", status_code=401)
                user.is_verified = True
                user.verification_code_hash = ""
                user.verification_expires_at = 0
                await self._upsert_user(user)

            tokens = self._issue_tokens(user)
            await self._store_refresh_token(user.user_id, tokens.refresh_token)
            return VerifyAccountResponse(user=self._to_profile(user), tokens=tokens)

    async def signin(self, payload: SigninRequest) -> tuple[UserProfile, AuthTokens]:
        self._ensure_enabled()
        async with self._lock:
            user = await self._get_user(payload.email)
            if user is None or not self._verify_password(payload.password, user.password_hash):
                raise AuthError("Invalid email or password", status_code=401)
            if not user.is_verified:
                raise AuthError("Account verification is required", status_code=403)

            tokens = self._issue_tokens(user)
            await self._prune_refresh_tokens(user.user_id)
            await self._store_refresh_token(user.user_id, tokens.refresh_token)
            return self._to_profile(user), tokens

    async def refresh(self, refresh_token: str) -> tuple[UserProfile, AuthTokens]:
        self._ensure_enabled()
        payload = self._decode_token(refresh_token, expected_type="refresh")
        email = str(payload["sub"]).lower()
        refresh_jti = str(payload["jti"])
        async with self._lock:
            user = await self._get_user(email)
            if user is None:
                raise AuthError("Account not found", status_code=404)
            is_valid = await self._refresh_token_is_valid(user.user_id, refresh_jti)
            if not is_valid:
                raise AuthError("Refresh token is no longer valid", status_code=401)

            await self._delete_refresh_token(user.user_id, refresh_jti)
            tokens = self._issue_tokens(user)
            await self._prune_refresh_tokens(user.user_id)
            await self._store_refresh_token(user.user_id, tokens.refresh_token)
            return self._to_profile(user), tokens

    async def get_user_from_access_token(self, token: str) -> UserProfile:
        self._ensure_enabled()
        payload = self._decode_token(token, expected_type="access")
        email = str(payload["sub"]).lower()
        user = await self._get_user(email)
        if user is None:
            raise AuthError("Account not found", status_code=404)
        if not user.is_verified:
            raise AuthError("Account is not verified", status_code=403)
        return self._to_profile(user)

    async def has_users(self) -> bool:
        return await asyncio.to_thread(self._count_users_sync) > 0

    def _ensure_enabled(self) -> None:
        if not self._settings.auth_enabled:
            raise AuthError("Authentication is disabled", status_code=503)

    def _initialize_sync(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL DEFAULT '',
                    password_hash TEXT NOT NULL,
                    is_verified INTEGER NOT NULL DEFAULT 0,
                    role TEXT NOT NULL DEFAULT 'user',
                    created_at INTEGER NOT NULL,
                    verification_code_hash TEXT NOT NULL DEFAULT '',
                    verification_expires_at INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS refresh_tokens (
                    user_id TEXT NOT NULL,
                    token_jti TEXT NOT NULL,
                    expires_at INTEGER NOT NULL,
                    PRIMARY KEY (user_id, token_jti),
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
                CREATE INDEX IF NOT EXISTS idx_refresh_expires ON refresh_tokens(expires_at);
                """
            )
            # Add self-healing check in case users table already exists without name column
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(users)")
            columns = [row[1] for row in cursor.fetchall()]
            if columns and "name" not in columns:
                conn.execute("ALTER TABLE users ADD COLUMN name TEXT NOT NULL DEFAULT ''")
            conn.commit()

    async def _get_user(self, email: str) -> UserRecord | None:
        return await asyncio.to_thread(self._get_user_sync, email)

    def _get_user_sync(self, email: str) -> UserRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT user_id, email, name, password_hash, is_verified, role, created_at,
                       verification_code_hash, verification_expires_at
                FROM users
                WHERE email = ?
                """,
                (email.lower(),),
            ).fetchone()
            if row is None:
                return None
            refresh_rows = conn.execute(
                """
                SELECT token_jti, expires_at
                FROM refresh_tokens
                WHERE user_id = ?
                """,
                (row["user_id"],),
            ).fetchall()
        return UserRecord(
            user_id=row["user_id"],
            email=row["email"],
            name=row["name"],
            password_hash=row["password_hash"],
            is_verified=bool(row["is_verified"]),
            role=row["role"],
            created_at=int(row["created_at"]),
            verification_code_hash=row["verification_code_hash"],
            verification_expires_at=int(row["verification_expires_at"]),
            active_refresh_tokens={item["token_jti"]: int(item["expires_at"]) for item in refresh_rows},
        )

    async def _upsert_user(self, user: UserRecord) -> None:
        await asyncio.to_thread(self._upsert_user_sync, user)

    def _upsert_user_sync(self, user: UserRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO users (
                    user_id, email, name, password_hash, is_verified, role, created_at,
                    verification_code_hash, verification_expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET
                    user_id = excluded.user_id,
                    name = excluded.name,
                    password_hash = excluded.password_hash,
                    is_verified = excluded.is_verified,
                    role = excluded.role,
                    created_at = excluded.created_at,
                    verification_code_hash = excluded.verification_code_hash,
                    verification_expires_at = excluded.verification_expires_at
                """,
                (
                    user.user_id,
                    user.email,
                    user.name,
                    user.password_hash,
                    int(user.is_verified),
                    user.role,
                    user.created_at,
                    user.verification_code_hash,
                    user.verification_expires_at,
                ),
            )
            conn.commit()
            conn.commit()

    async def _store_refresh_token(self, user_id: str, refresh_token: str) -> None:
        payload = self._decode_token(refresh_token, expected_type="refresh")
        await asyncio.to_thread(
            self._store_refresh_token_sync,
            user_id,
            str(payload["jti"]),
            int(payload["exp"]),
        )

    def _store_refresh_token_sync(self, user_id: str, token_jti: str, expires_at: int) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO refresh_tokens (user_id, token_jti, expires_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, token_jti) DO UPDATE SET expires_at = excluded.expires_at
                """,
                (user_id, token_jti, expires_at),
            )
            conn.commit()

    async def _refresh_token_is_valid(self, user_id: str, token_jti: str) -> bool:
        return await asyncio.to_thread(self._refresh_token_is_valid_sync, user_id, token_jti)

    def _refresh_token_is_valid_sync(self, user_id: str, token_jti: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT expires_at
                FROM refresh_tokens
                WHERE user_id = ? AND token_jti = ?
                """,
                (user_id, token_jti),
            ).fetchone()
            if row is None:
                return False
            return int(row["expires_at"]) >= int(time.time())

    async def _delete_refresh_token(self, user_id: str, token_jti: str) -> None:
        await asyncio.to_thread(self._delete_refresh_token_sync, user_id, token_jti)

    def _delete_refresh_token_sync(self, user_id: str, token_jti: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM refresh_tokens WHERE user_id = ? AND token_jti = ?",
                (user_id, token_jti),
            )
            conn.commit()

    async def _delete_refresh_tokens_for_user(self, user_id: str) -> None:
        await asyncio.to_thread(self._delete_refresh_tokens_for_user_sync, user_id)

    def _delete_refresh_tokens_for_user_sync(self, user_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM refresh_tokens WHERE user_id = ?", (user_id,))
            conn.commit()

    async def _prune_refresh_tokens(self, user_id: str) -> None:
        await asyncio.to_thread(self._prune_refresh_tokens_sync, user_id)

    def _prune_refresh_tokens_sync(self, user_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM refresh_tokens WHERE user_id = ? AND expires_at < ?",
                (user_id, int(time.time())),
            )
            conn.commit()

    async def _determine_role(self, email: str) -> str:
        if self._settings.auth_bootstrap_admin_email:
            return "admin" if email == self._settings.auth_bootstrap_admin_email.lower() else "user"
        has_users = await self.has_users()
        return "admin" if not has_users else "user"

    def _count_users_sync(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS count FROM users").fetchone()
            return int(row["count"]) if row is not None else 0

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA synchronous=NORMAL")
        return connection

    def _issue_tokens(self, user: UserRecord) -> AuthTokens:
        now = int(time.time())
        access_token = self._encode_token(
            {
                "sub": user.email,
                "role": user.role,
                "type": "access",
                "iat": now,
                "exp": now + self._settings.auth_access_token_ttl_seconds,
            }
        )
        refresh_jti = uuid.uuid4().hex
        refresh_token = self._encode_token(
            {
                "sub": user.email,
                "type": "refresh",
                "jti": refresh_jti,
                "iat": now,
                "exp": now + self._settings.auth_refresh_token_ttl_seconds,
            }
        )
        return AuthTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self._settings.auth_access_token_ttl_seconds,
        )

    def _encode_token(self, payload: dict[str, object]) -> str:
        return jwt.encode(payload, self._settings.auth_secret_key, algorithm="HS256")

    def _decode_token(self, token: str, *, expected_type: str) -> dict[str, object]:
        try:
            payload = jwt.decode(token, self._settings.auth_secret_key, algorithms=["HS256"])
        except jwt.ExpiredSignatureError as exc:
            raise AuthError("Token expired", status_code=401) from exc
        except jwt.PyJWTError as exc:
            raise AuthError("Invalid token", status_code=401) from exc
        
        if payload.get("type") != expected_type:
            raise AuthError("Token type mismatch", status_code=401)
        return payload

    def _hash_password(self, password: str) -> str:
        return pwd_context.hash(password)

    def _verify_password(self, password: str, encoded_hash: str) -> bool:
        if "." in encoded_hash:
            try:
                encoded_salt, encoded_digest = encoded_hash.split(".", 1)
                salt = self._b64decode(encoded_salt)
                expected = self._b64decode(encoded_digest)
                derived = hashlib.pbkdf2_hmac(
                    "sha256",
                    password.encode("utf-8"),
                    salt,
                    200_000,
                )
                if hmac.compare_digest(derived, expected):
                    return True
            except Exception:
                pass

        try:
            return pwd_context.verify(password, encoded_hash)
        except Exception:
            return False

    def _hash_code(self, code: str) -> str:
        digest = hashlib.sha256(
            f"{self._settings.auth_secret_key}:{code}".encode("utf-8")
        ).digest()
        return self._b64encode(digest)

    def _generate_code(self) -> str:
        return f"{secrets.randbelow(1_000_000):06d}"

    def _deliver_verification_code(self, email: str, code: str) -> None:
        logger.info("Verification code generated for %s: %s", email, code)

    def _maybe_expose_code(self, code: str) -> str | None:
        if self._settings.debug or self._settings.auth_verification_delivery == "inline":
            return code
        return None

    def _to_profile(self, user: UserRecord) -> UserProfile:
        return UserProfile(
            user_id=user.user_id,
            email=user.email,
            name=user.name,
            is_verified=user.is_verified,
            role=user.role,
            created_at=user.created_at,
        )

    @staticmethod
    def _b64encode(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("utf-8")

    @staticmethod
    def _b64decode(value: str) -> bytes:
        padding = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode((value + padding).encode("utf-8"))
