from backend.app.config import settings
from backend.app.services.transport.base import TransportBase
from backend.app.services.transport.http_transport import HttpTransport
from backend.app.services.transport.bluetooth_transport import BluetoothTransport
from backend.app.services.transport.simulated_transport import SimulatedTransport

_transport_instance: TransportBase | None = None


def get_transport() -> TransportBase:
    """Return the configured transport adapter (singleton)."""
    global _transport_instance
    if _transport_instance is None:
        if settings.transport_mode == "simulate":
            _transport_instance = SimulatedTransport()
        elif settings.transport_mode == "bluetooth":
            _transport_instance = BluetoothTransport()
        else:
            _transport_instance = HttpTransport()
    return _transport_instance
