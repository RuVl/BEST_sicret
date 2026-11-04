from .client import AwgClient, get_awg_client
from .exceptions import AwgAccessRevokedError, AwgDeviceLimitError, AwgError
from .identity import (
    MAX_DEVICE_LABEL_LEN,
    DeviceLabelError,
    device_client_name,
    fallback_device_client_name,
    free_device_number,
    is_valid_client_name,
    normalize_device_label,
)
from .platform import PLATFORMS, DevicePlatform, excluded_apps, is_platform, personalize_config
from .qr import render_config_qr
from .schemas import AwgPeer
from .service import (
    IssuedConfig,
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
from .share_link import extract_device_config

__all__ = [
    "PLATFORMS",
    "DevicePlatform",
    "excluded_apps",
    "is_platform",
    "personalize_config",
    "MAX_DEVICE_LABEL_LEN",
    "AwgAccessRevokedError",
    "AwgClient",
    "AwgDeviceLimitError",
    "AwgError",
    "AwgPeer",
    "add_device",
    "device_client_name",
    "fallback_device_client_name",
    "device_limit",
    "disable_peers",
    "ensure_peer",
    "extract_device_config",
    "free_device_number",
    "get_awg_client",
    "is_valid_client_name",
    "DeviceLabelError",
    "normalize_device_label",
    "IssuedConfig",
    "issue_device_config",
    "peers_by_name",
    "remove_device",
    "remove_peers",
    "rename_device",
    "render_config_qr",
    "restore_access",
]
