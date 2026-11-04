from .identity import build_client_email, fallback_client_email, is_valid_client_id
from .panel import PANEL_ERRORS, get_xui_api, is_auth_error, panel_error_text, raise_for_skipped, set_clients_enabled
from .service import (
    ensure_subscription,
    issue_subscription,
    reissue_subscription,
    restore_subscription,
    subscription_url,
)

__all__ = [
    "PANEL_ERRORS",
    "build_client_email",
    "ensure_subscription",
    "fallback_client_email",
    "get_xui_api",
    "is_auth_error",
    "is_valid_client_id",
    "issue_subscription",
    "panel_error_text",
    "raise_for_skipped",
    "reissue_subscription",
    "restore_subscription",
    "set_clients_enabled",
    "subscription_url",
]
