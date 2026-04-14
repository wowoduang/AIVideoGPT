from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from dataclasses import dataclass
from typing import Dict, Optional

from app.utils import workspace


@dataclass
class StoredUser:
    name: str
    email: str
    password_hash: str
    salt: str
    created_at: str


def _auth_root() -> str:
    return workspace.state_dir("auth", create=True)


def _users_path() -> str:
    return os.path.join(_auth_root(), "users.json")


def _sessions_path() -> str:
    return os.path.join(_auth_root(), "sessions.json")


def _read_json(path: str) -> Dict[str, Dict]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError:
        return {}


def _write_json(path: str, payload: Dict[str, Dict]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _hash_password(password: str, salt: bytes) -> str:
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120000)
    return base64.b64encode(hashed).decode("utf-8")


def _encode_salt(raw: bytes) -> str:
    return base64.b64encode(raw).decode("utf-8")


def _decode_salt(encoded: str) -> bytes:
    return base64.b64decode(encoded.encode("utf-8"))


def _load_users() -> Dict[str, StoredUser]:
    data = _read_json(_users_path())
    users: Dict[str, StoredUser] = {}
    for email, payload in data.items():
        users[email] = StoredUser(
            name=payload["name"],
            email=email,
            password_hash=payload["password_hash"],
            salt=payload["salt"],
            created_at=payload["created_at"],
        )
    return users


def _save_users(users: Dict[str, StoredUser]) -> None:
    data: Dict[str, Dict[str, str]] = {}
    for email, user in users.items():
        data[email] = {
            "name": user.name,
            "password_hash": user.password_hash,
            "salt": user.salt,
            "created_at": user.created_at,
        }
    _write_json(_users_path(), data)


def _load_sessions() -> Dict[str, Dict[str, str]]:
    return _read_json(_sessions_path())


def _save_sessions(sessions: Dict[str, Dict[str, str]]) -> None:
    _write_json(_sessions_path(), sessions)


def register_user(name: str, email: str, password: str, created_at: str) -> StoredUser:
    users = _load_users()
    if email in users:
        raise ValueError("email_exists")
    salt = os.urandom(16)
    password_hash = _hash_password(password, salt)
    user = StoredUser(
        name=name,
        email=email,
        password_hash=password_hash,
        salt=_encode_salt(salt),
        created_at=created_at,
    )
    users[email] = user
    _save_users(users)
    return user


def authenticate(email: str, password: str) -> Optional[StoredUser]:
    users = _load_users()
    user = users.get(email)
    if not user:
        return None
    salt = _decode_salt(user.salt)
    password_hash = _hash_password(password, salt)
    if password_hash != user.password_hash:
        return None
    return user


def create_session(email: str, created_at: str) -> str:
    sessions = _load_sessions()
    token = secrets.token_urlsafe(32)
    sessions[token] = {"email": email, "created_at": created_at, "last_seen": created_at}
    _save_sessions(sessions)
    return token


def touch_session(token: str, seen_at: str) -> None:
    sessions = _load_sessions()
    payload = sessions.get(token)
    if not payload:
        return
    payload["last_seen"] = seen_at
    sessions[token] = payload
    _save_sessions(sessions)


def get_user_by_token(token: str) -> Optional[StoredUser]:
    sessions = _load_sessions()
    payload = sessions.get(token)
    if not payload:
        return None
    users = _load_users()
    return users.get(payload["email"])


def revoke_token(token: str) -> bool:
    sessions = _load_sessions()
    if token not in sessions:
        return False
    sessions.pop(token, None)
    _save_sessions(sessions)
    return True
