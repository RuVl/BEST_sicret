"""QR с урезанным списком исключений: файл - полный, в QR - сколько влезет."""

from includes.awg import excluded_apps, personalize_config
from includes.awg.qr import _encode, fit_config_qr

CONF = """[Interface]
PrivateKey = 3333333333333333333333333333333333333333333=
Address = 10.70.0.2/32
DNS = 1.1.1.1
Jc = 4
Jmin = 10
Jmax = 50
S1 = 72
S2 = 56
S3 = 32
S4 = 16
H1 = 1
H2 = 2
H3 = 3
H4 = 4
I1 = <r 2><b 0x858000010002000000001c><rc 28><b 0x0463646e730669636c6f756403636f6d0000010001>

[Peer]
PublicKey = 2sVFRwz1Yr8wH0bD4p1QKjr5tL6V8qMg0aF0nYz7v3E=
AllowedIPs = 0.0.0.0/0
Endpoint = 45.136.228.156:443
"""


def _builder(platform: str):
    apps = excluded_apps()

    def build(count: int) -> str:
        return personalize_config(CONF, platform, name="BEST VPN", excluded=apps[:count])

    return build, len(apps)


def test_android_qr_is_truncated_to_maximum_that_fits():
    build, total = _builder("android")
    fitted = fit_config_qr(build, total)

    assert fitted is not None
    assert fitted.png.startswith(b"\x89PNG")
    assert 0 < fitted.included < total  # весь список не влезает, но банки и госуслуги - да
    assert fitted.truncated
    assert _encode(build(fitted.included + 1)) is None  # взяли максимум


def test_other_platforms_not_truncated():
    build, total = _builder("ios")  # исключения пишутся только для Android
    fitted = fit_config_qr(build, total)

    assert fitted is not None and not fitted.truncated


def test_nothing_fits():
    assert fit_config_qr(lambda count: "x" * 8000, 10) is None


class _Client:
    async def get_config(self, peer):
        return CONF


def _issue(monkeypatch, platform: str):
    import asyncio
    from types import SimpleNamespace

    from includes.awg import service

    async def nothing(*args, **kwargs):
        return None

    monkeypatch.setattr(service, "_ensure_usable", nothing)
    monkeypatch.setattr(service, "ensure_peer", nothing)
    monkeypatch.setattr(service, "mark_issued", nothing)
    device = SimpleNamespace(platform=platform)
    return asyncio.run(service.issue_device_config(None, _Client(), None, device, None))


def test_issued_android_file_is_full_and_qr_is_truncated(monkeypatch):
    issued = _issue(monkeypatch, "android")
    apps = excluded_apps()

    assert f"ExcludedApplications = {','.join(apps)}" in issued.text
    assert issued.qr is not None and issued.qr.truncated and issued.qr.total == len(apps)


def test_issued_ios_has_full_qr(monkeypatch):
    issued = _issue(monkeypatch, "ios")

    assert "ExcludedApplications" not in issued.text
    assert issued.qr is not None and not issued.qr.truncated
