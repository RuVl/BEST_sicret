from .client import XuiClient, close_xui_client, get_xui_client
from .exceptions import XuiAuthError, XuiClientNotFoundError, XuiError
from .identity import build_client_email, fallback_client_email, is_valid_client_id
from .schemas import ClientRecord, ClientTraffic, XuiClientPayload
from .service import ensure_subscription, issue_subscription, reissue_subscription, restore_subscription

__all__ = [
    "ClientRecord",
    "ClientTraffic",
    "XuiAuthError",
    "XuiClient",
    "XuiClientNotFoundError",
    "XuiClientPayload",
    "XuiError",
    "build_client_email",
    "close_xui_client",
    "ensure_subscription",
    "fallback_client_email",
    "get_xui_client",
    "is_valid_client_id",
    "issue_subscription",
    "reissue_subscription",
    "restore_subscription",
]
