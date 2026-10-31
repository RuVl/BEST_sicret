from .client import AwgClient, get_awg_client
from .config import build_client_config, effective_mtu
from .exceptions import AwgAccessRevokedError, AwgAuthError, AwgDeviceLimitError, AwgError
from .identity import (
    MAX_DEVICE_LABEL_LEN,
    build_peer_comment,
    device_client_name,
    free_device_number,
    is_valid_client_name,
    normalize_device_label,
)
from .qr import render_config_qr
from .schemas import AwgClientPayload, AwgInbound, AwgPeer, AwgServer
from .service import (
    add_device,
    device_limit,
    disable_peers,
    ensure_peer,
    issue_device_config,
    peers_by_name,
    remove_device,
    remove_peers,
    rename_device,
    restore_access,
)

__all__ = [
    "MAX_DEVICE_LABEL_LEN",
    "AwgAccessRevokedError",
    "AwgAuthError",
    "AwgClient",
    "AwgClientPayload",
    "AwgDeviceLimitError",
    "AwgError",
    "AwgInbound",
    "AwgPeer",
    "AwgServer",
    "add_device",
    "build_client_config",
    "build_peer_comment",
    "device_client_name",
    "device_limit",
    "disable_peers",
    "effective_mtu",
    "ensure_peer",
    "free_device_number",
    "get_awg_client",
    "is_valid_client_name",
    "normalize_device_label",
    "issue_device_config",
    "peers_by_name",
    "remove_device",
    "remove_peers",
    "rename_device",
    "render_config_qr",
    "restore_access",
]
