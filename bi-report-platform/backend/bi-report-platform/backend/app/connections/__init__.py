"""Connections to the business databases that reports query (week 1 of the build plan)."""

from ..models import DataConnection
from . import crypto
from .engines import ConnSpec
from .openpages import OPSpec


def connection_spec(c: DataConnection) -> ConnSpec:
    """Raises crypto.ConnectionsKeyError if the saved password can't be decrypted."""
    return ConnSpec(db_type=c.db_type, host=c.host, port=c.port, database=c.database, username=c.username,
                    password=crypto.decrypt(c.password_encrypted), options=c.options or {})


def openpages_spec(c: DataConnection, password: str | None = None, client_key: str | None = None) -> OPSpec:
    """Sign-in details for an OpenPages connection. password / client_key override the saved ones
    (used to test the form before saving). Raises crypto.ConnectionsKeyError like connection_spec."""
    o = c.options or {}
    if password is None:
        password = crypto.decrypt(c.password_encrypted)
    if client_key is None:
        client_key = crypto.decrypt(o.get("client_key_encrypted", ""))
    return OPSpec(base_url=c.host, auth_type=o.get("auth_type", "basic"), username=c.username, secret=password,
                  client_id=o.get("client_id", ""), token_url=o.get("token_url", ""),
                  client_cert=o.get("client_cert", ""), client_key=client_key,
                  verify=not o.get("trust_server_certificate", False))
