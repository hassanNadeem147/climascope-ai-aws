import base64
import binascii
import hashlib
import hmac
import json
import secrets
import time
from collections.abc import Mapping
from typing import Any
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_MAXMEM = 64 * 1024 * 1024
_PASSWORD_HASH_BYTES = 32
_JWT_ALGORITHM = "HS256"
class InvalidTokenError(ValueError):
    """Raised when a JWT is malformed, expired, or fails verification."""
def hash_password(password: str) -> str:
    """Hash a password with scrypt and return a self-describing encoded value."""
    if not isinstance(password, str) or not password:
        raise ValueError("Password must be a non-empty string.")
    salt = secrets.token_bytes(16)
    derived_key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_PASSWORD_HASH_BYTES,
        maxmem=_SCRYPT_MAXMEM,
    )
    return "$".join(
        (
            "scrypt",
            str(_SCRYPT_N),
            str(_SCRYPT_R),
            str(_SCRYPT_P),
            _base64url_encode(salt),
            _base64url_encode(derived_key),
        )
    )
def verify_password(password: str, password_hash: str) -> bool:
    """Check a plaintext password against a value returned by hash_password."""
    if not isinstance(password, str) or not isinstance(password_hash, str):
        return False
    try:
        scheme, n_value, r_value, p_value, salt_value, hash_value = (
            password_hash.split("$")
        )
        if scheme != "scrypt":
            return False
        n, r, p = int(n_value), int(r_value), int(p_value)
        if not (2**14 <= n <= 2**18 and n & (n - 1) == 0):
            return False
        if not (1 <= r <= 16 and 1 <= p <= 4):
            return False
        salt = _base64url_decode(salt_value)
        expected_hash = _base64url_decode(hash_value)
        if not 16 <= len(salt) <= 64 or len(expected_hash) != _PASSWORD_HASH_BYTES:
            return False
        actual_hash = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            dklen=len(expected_hash),
            maxmem=_SCRYPT_MAXMEM,
        )
    except (ValueError, TypeError, binascii.Error, OverflowError):
        return False
    return hmac.compare_digest(actual_hash, expected_hash)
def create_access_token(
    claims: Mapping[str, Any],
    secret_key: str,
    expires_in_seconds: int = 30 * 60,
) -> str:
    """Create an HS256 JWT access token with issued-at and expiry claims."""
    if not isinstance(secret_key, str) or len(secret_key.encode("utf-8")) < 32:
        raise ValueError("JWT secret key must be at least 32 bytes.")
    if not isinstance(expires_in_seconds, int) or isinstance(expires_in_seconds, bool):
        raise ValueError("Token lifetime must be a positive integer.")
    if expires_in_seconds <= 0:
        raise ValueError("Token lifetime must be a positive integer.")
    payload = dict(claims)
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise ValueError("JWT claims must include a non-empty 'sub' string.")
    if "exp" in payload or "iat" in payload:
        raise ValueError("'exp' and 'iat' claims are set by the token helper.")
    issued_at = int(time.time())
    payload["iat"] = issued_at
    payload["exp"] = issued_at + expires_in_seconds
    header = {"alg": _JWT_ALGORITHM, "typ": "JWT"}

    encoded_header = _base64url_encode(
        json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    encoded_payload = _base64url_encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signing_input = f"{encoded_header}.{encoded_payload}"
    signature = hmac.new(
        secret_key.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_base64url_encode(signature)}"
def decode_access_token(
    token: str,
    secret_key: str,
    *,
    leeway_seconds: int = 0,
) -> dict[str, Any]:
    """Verify an HS256 JWT, validate its subject and expiry, and return its claims."""
    if not isinstance(secret_key, str) or len(secret_key.encode("utf-8")) < 32:
        raise ValueError("JWT secret key must be at least 32 bytes.")
    if (
        not isinstance(leeway_seconds, int)
        or isinstance(leeway_seconds, bool)
        or leeway_seconds < 0
    ):
        raise ValueError("Token leeway must be a non-negative integer.")
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
        header = json.loads(_base64url_decode(encoded_header))
        claims = json.loads(_base64url_decode(encoded_payload))
        signature = _base64url_decode(encoded_signature)
    except (AttributeError, ValueError, TypeError, binascii.Error, json.JSONDecodeError):
        raise InvalidTokenError("Invalid access token.") from None
    if not isinstance(header, dict) or header.get("alg") != _JWT_ALGORITHM:
        raise InvalidTokenError("Invalid access token.")
    if header.get("typ") != "JWT" or not isinstance(claims, dict):
        raise InvalidTokenError("Invalid access token.")
    signing_input = f"{encoded_header}.{encoded_payload}"
    expected_signature = hmac.new(
        secret_key.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(signature, expected_signature):
        raise InvalidTokenError("Invalid access token.")
    subject = claims.get("sub")
    expiry = claims.get("exp")
    not_before = claims.get("nbf", 0)
    now = time.time()
    if (
        not isinstance(subject, str)
        or not subject.strip()
        or not isinstance(expiry, (int, float))
        or isinstance(expiry, bool)
        or not isinstance(not_before, (int, float))
        or isinstance(not_before, bool)
        or expiry <= now - leeway_seconds
        or not_before > now + leeway_seconds
    ):
        raise InvalidTokenError("Invalid or expired access token.")
    return claims
def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")
def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.b64decode(
        f"{value}{padding}",
        altchars=b"-_",
        validate=True,
    )