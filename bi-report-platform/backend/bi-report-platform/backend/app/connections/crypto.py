from cryptography.fernet import Fernet, InvalidToken

from ..config import settings


class ConnectionsKeyError(Exception):
    """CONNECTIONS_KEY is missing, invalid, or not the key the secrets were saved with."""


def _fernet() -> Fernet:
    if not settings.connections_key:
        raise ConnectionsKeyError(
            "CONNECTIONS_KEY is not set in backend/.env, so database passwords and AI API keys can't be stored "
            "safely. See README Part 9.")
    try:
        return Fernet(settings.connections_key.encode())
    except ValueError as err:
        raise ConnectionsKeyError("CONNECTIONS_KEY in backend/.env is not a valid Fernet key.") from err


def encrypt(password: str) -> str:
    return _fernet().encrypt(password.encode()).decode() if password else ""


def decrypt(token: str) -> str:
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as err:
        raise ConnectionsKeyError(
            "A saved password or API key can't be decrypted because CONNECTIONS_KEY has changed since it was "
            "saved. Restore the old key, or edit the item and enter the password or key again.") from err
