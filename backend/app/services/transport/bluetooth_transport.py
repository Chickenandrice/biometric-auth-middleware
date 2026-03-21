import asyncio
import json
import logging

from backend.app.config import settings
from backend.app.schemas.auth import VerificationPayload
from backend.app.schemas.enrollment import EnrollmentPayload
from backend.app.services.transport.base import TransportBase

logger = logging.getLogger(__name__)

# BLE GATT characteristic UUIDs (must match edge device)
SERVICE_UUID = "12345678-1234-5678-1234-56789abcdef0"
COMMAND_CHAR_UUID = "12345678-1234-5678-1234-56789abcdef1"
DATA_CHAR_UUID = "12345678-1234-5678-1234-56789abcdef2"


class BluetoothTransport(TransportBase):
    """Communicates with the edge device over Bluetooth Low Energy."""

    def __init__(self, address: str | None = None):
        self.address = address or settings.edge_bluetooth_address

    async def _send_command_and_receive(self, command: dict) -> dict:
        """Send a JSON command via BLE and read back the response."""
        try:
            from bleak import BleakClient
        except ImportError:
            raise RuntimeError("bleak is required for Bluetooth transport: pip install bleak")

        async with BleakClient(self.address, timeout=30.0) as client:
            cmd_bytes = json.dumps(command).encode("utf-8")
            await client.write_gatt_char(COMMAND_CHAR_UUID, cmd_bytes)

            # Wait for the edge device to process and write response
            await asyncio.sleep(5.0)

            data = await client.read_gatt_char(DATA_CHAR_UUID)
            return json.loads(data.decode("utf-8"))

    async def request_verification(self, user_id: str) -> VerificationPayload:
        result = await self._send_command_and_receive({
            "user_id": user_id,
            "mode": "verify",
        })
        return VerificationPayload(**result)

    async def request_enrollment(self, user_id: str) -> EnrollmentPayload:
        result = await self._send_command_and_receive({
            "user_id": user_id,
            "mode": "enroll",
        })
        return EnrollmentPayload(**result)

    async def health_check(self) -> bool:
        try:
            from bleak import BleakClient
            async with BleakClient(self.address, timeout=5.0) as client:
                return client.is_connected
        except Exception:
            return False
