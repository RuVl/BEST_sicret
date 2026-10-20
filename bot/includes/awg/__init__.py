from .client import AwgClient, close_awg_client, get_awg_client
from .exceptions import AwgAccessRevokedError, AwgAuthError, AwgDeviceLimitError, AwgError, AwgPeerNotFoundError
from .identity import build_peer_comment, device_client_name, free_device_number, is_valid_client_name
from .qr import render_config_qr
from .schemas import AwgPeer
from .service import (
    add_device,
    device_limit,
    disable_peers,
    ensure_peer,
    issue_device_config,
    peers_by_name,
    remove_device,
    remove_peers,
    restore_access,
)

__all__ = [
    "AwgAccessRevokedError",
    "AwgAuthError",
    "AwgClient",
    "AwgDeviceLimitError",
    "AwgError",
    "AwgPeer",
    "AwgPeerNotFoundError",
    "add_device",
    "build_peer_comment",
    "close_awg_client",
    "device_client_name",
    "device_limit",
    "disable_peers",
    "ensure_peer",
    "free_device_number",
    "get_awg_client",
    "is_valid_client_name",
    "issue_device_config",
    "peers_by_name",
    "remove_device",
    "remove_peers",
    "render_config_qr",
    "restore_access",
]
