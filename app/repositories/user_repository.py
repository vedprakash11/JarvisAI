"""MySQL implementation of UserRepository. Delegates to app.db (single place for init/connection)."""
from typing import Optional

from app.db import create_user as _create_user, get_user_by_email as _get_by_email, get_user_by_id as _get_by_id


class MySQLUserRepository:
    """User persistence in MySQL. Uses app.db for connections and init_db at startup."""

    def get_by_id(self, user_id: int) -> Optional[dict]:
        return _get_by_id(user_id)

    def get_by_email(self, email: str) -> Optional[dict]:
        return _get_by_email(email)

    def create(self, email: str, password_hash: str, name: str = "") -> int:
        return _create_user(email, password_hash, name)
