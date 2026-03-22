import asyncio
import struct
import max30102
import hrcalc
from bless import (BlessServer, GATTCharacteristicProperties, GATTAttributePermissions)

SERVICE_UUID        = "12345678-1234-5678-1234-56789abcdef0"
CHARACTERISTIC_UUID = "12345678-1234-5678-1234-56789abcdef1"

m = max30102.MAX30102()
client_connected = asyncio.Event()

def on_connect(server: BlessServer):
    print("✅ Client connected — starting data stream...")
    client_connected.set()

def on_disconnect(server: BlessServer):
    print("❌ Client disconnected — pausing stream...")
    client_connected.clear()

async def stream_data(server: BlessServer):
    while True:
        await client_connected.wait()
        red, ir = m.read_sequential()
        if len(red) > 0 and len(ir) > 0:
            hr, hr_valid, spo2, spo2_valid = hrcalc.calc_hr_and_spo2(ir, red)
            if hr_valid and spo2_valid:
                print(f"Sending → BPM: {hr:.1f}   SpO2: {spo2:.1f}%")
                payload = struct.pack(">ff", float(hr), float(spo2))
                server.get_characteristic(CHARACTERISTIC_UUID).value = bytearray(payload)
                server.update_value(SERVICE_UUID, CHARACTERISTIC_UUID)
        await asyncio.sleep(1)  # Send exactly once per second

async def run():
    server = BlessServer(name="MAX30102_Pi5")
    server.read_request_func  = lambda char, **kwargs: char.value
    server.write_request_func = lambda char, value, **kwargs: None
    server.on_connect_func    = on_connect
    server.on_disconnect_func = on_disconnect

    await server.add_new_service(SERVICE_UUID)
    await server.add_new_characteristic(
        SERVICE_UUID,
        CHARACTERISTIC_UUID,
        GATTCharacteristicProperties.read | GATTCharacteristicProperties.notify,
        None,
        GATTAttributePermissions.readable
    )

    await server.start()
    print("📡 Advertising as 'MAX30102_Pi5' — waiting for connection...")
    await stream_data(server)

asyncio.run(run())
