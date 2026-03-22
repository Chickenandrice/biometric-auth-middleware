import time
import struct
from collections import deque

import numpy as np
from scipy.signal import find_peaks
import smbus2
from gpiozero import DigitalInputDevice

# ── ADS1115 direct I2C config ────────────────────────────
ADS1115_ADDR    = 0x48
REG_CONVERSION  = 0x00
REG_CONFIG      = 0x01

# Config register:
# OS=1 (start conversion), MUX=100 (AIN0 vs GND),
# PGA=001 (±4.096V), MODE=0 (continuous),
# DR=111 (860 SPS), COMP all disabled
CONFIG_CONTINUOUS_A0 = [0xC3, 0xE3]  # MSB, LSB

def ads_init(bus):
    bus.write_i2c_block_data(ADS1115_ADDR, REG_CONFIG, CONFIG_CONTINUOUS_A0)
    time.sleep(0.01)

def ads_read(bus):
    raw = bus.read_i2c_block_data(ADS1115_ADDR, REG_CONVERSION, 2)
    value = struct.unpack('>h', bytes(raw))[0]  # Signed 16-bit big-endian
    voltage = value * 4.096 / 32767.0           # Convert to volts (gain=1)
    return voltage

# ── Lead-off pins ────────────────────────────────────────
LO_PLUS  = DigitalInputDevice(17)
LO_MINUS = DigitalInputDevice(27)

# ── Signal constants ─────────────────────────────────────
SIGNAL_LEN  = 188
FS          = 860
BUFFER_LEN  = FS * 5  # 5-second rolling buffer

buffer        = deque(maxlen=BUFFER_LEN)
last_peak_idx = -9999

# ── Signal processing ────────────────────────────────────
def preprocess(sig):
    x = np.asarray(sig, dtype=np.float32)
    x = x - np.mean(x)                                    # Remove DC offset
    x = x - np.convolve(x, np.ones(25) / 25, mode='same') # Remove baseline drift
    x = (x - x.min()) / (x.max() - x.min() + 1e-8)       # Normalize to [0, 1]
    return x

def extract_window(signal, peak_idx, pre=60, post=127):
    start = peak_idx - pre
    end   = peak_idx + post + 1
    if start < 0 or end > len(signal):
        return None
    window = signal[start:end]
    if len(window) != SIGNAL_LEN:
        x_old  = np.linspace(0, 1, len(window))
        x_new  = np.linspace(0, 1, SIGNAL_LEN)
        window = np.interp(x_new, x_old, window)
    return window.astype(np.float32)

def detect_r_peaks(signal):
    x = preprocess(signal)
    peaks, _ = find_peaks(
        x,
        distance=int(0.25 * FS),  # Min 250ms between peaks (~240 BPM max)
        prominence=0.05            # Must stand out from baseline
    )
    return peaks

# ── Main loop ────────────────────────────────────────────
print("Collecting ECG... Press Ctrl+C to stop.")

with smbus2.SMBus(1) as bus:
    ads_init(bus)
    try:
        while True:
            if LO_PLUS.value or LO_MINUS.value:
                print("⚠ Lead off — check electrodes")
                time.sleep(0.01)
                continue

            buffer.append(ads_read(bus))

            if len(buffer) < BUFFER_LEN:
                continue

            signal = np.array(buffer, dtype=np.float32)
            peaks  = detect_r_peaks(signal)

            for peak in peaks:
                # Skip peaks too close to the last one
                if peak - last_peak_idx < int(0.3 * FS):
                    continue

                window = extract_window(signal, peak)
                if window is None:
                    continue

                last_peak_idx = peak
                beat_tensor   = window.reshape(1, 1, SIGNAL_LEN)

                print(f"✅ Beat window ready — peak @ sample {peak}")
                print(f"   Shape: {beat_tensor.shape}")
                print(f"   First 5 values: {beat_tensor[0,0,:5]}")

            time.sleep(1.0 / FS)

    except KeyboardInterrupt:
        print("\nStopped.")
