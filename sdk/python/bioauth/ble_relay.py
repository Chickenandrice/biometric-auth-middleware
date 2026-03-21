"""
Subscribe to a BLE notify characteristic and forward JSON payloads to the gateway.

Requires ``bleak`` (already in the main project requirements).

Example::

    import asyncio
    from bioauth import BioAuthClient, relay_notifications

    async def main():
        client = BioAuthClient()
        await relay_notifications(
            client,
            ble_address="AA:BB:CC:DD:EE:FF",
            service_uuid="6e400001-b5a3-f393-e0a9-e50e24dcca9e",
            char_uuid="6e400003-b5a3-f393-e0a9-e50e24dcca9e",
            mode="enroll",  # or \"auth\" with user_id + action
        )

    asyncio.run(main())
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Literal

logger = logging.getLogger(__name__)

Mode = Literal["enroll", "auth"]


async def relay_notifications(
    client: Any,
    ble_address: str,
    service_uuid: str,
    char_uuid: str,
    *,
    mode: Mode = "enroll",
    auth_user_id: str | None = None,
    auth_action: str | None = None,
    auth_risk_level: str = "high",
) -> None:
    """
    Connect with bleak, start notifications, parse UTF-8 JSON, call relay_* on ``client``.

    ``client`` must be a :class:`BioAuthClient` with ``relay_enrollment`` / ``relay_authorize``.
    """
    try:
        from bleak import BleakClient
    except ImportError as e:
        raise RuntimeError("bleak is required: pip install bleak") from e

    def _on_notify(_handle: int, data: bytearray) -> None:
        try:
            obj = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as ex:
            logger.warning("Skip non-JSON BLE packet: %s", ex)
            return
        try:
            if mode == "enroll":
                r = client.relay_enrollment(obj)
            else:
                if not auth_user_id or not auth_action:
                    logger.error("auth mode requires auth_user_id and auth_action")
                    return
                obj = {**obj, "user_id": auth_user_id, "mode": obj.get("mode", "verify")}
                r = client.relay_authorize(
                    auth_user_id,
                    auth_action,
                    obj,
                    risk_level=auth_risk_level,
                )
            logger.info("Relay OK: %s", r)
        except Exception as ex:
            logger.exception("Relay failed: %s", ex)

    async with BleakClient(ble_address, timeout=30.0) as ble:
        await ble.start_notify(char_uuid, _on_notify)
        logger.info(
            "BLE connected; waiting for JSON on %s / %s (mode=%s). Stops when device disconnects.",
            service_uuid,
            char_uuid,
            mode,
        )
        try:
            while ble.is_connected:
                await asyncio.sleep(0.5)
        finally:
            try:
                await ble.stop_notify(char_uuid)
            except Exception:
                pass
