from ecg_window import *
import numpy as np

YOUR_NAME = "Varun"        # Change to your actual name
N_BEATS   = 100            # Collect 100 beats for enrollment

collected = []
print(f"Collecting {N_BEATS} beats for {YOUR_NAME}...")
print("Place electrodes and stay still...")

with smbus2.SMBus(1) as bus:
    ads_init(bus)
    try:
        while len(collected) < N_BEATS:
            if LO_PLUS.value or LO_MINUS.value:
                time.sleep(0.01)
                continue

            buffer.append(ads_read(bus))

            if len(buffer) < BUFFER_LEN:
                continue

            signal = np.array(buffer, dtype=np.float32)
            peaks  = detect_r_peaks(signal)

            for peak in peaks:
                global last_peak_idx
                if peak - last_peak_idx < int(0.3 * FS):
                    continue
                window = extract_window(signal, peak)
                if window is None:
                    continue
                last_peak_idx = peak
                collected.append(window)
                print(f"  Beat {len(collected)}/{N_BEATS} captured")

            time.sleep(1.0 / FS)

    except KeyboardInterrupt:
        pass

np.save(f"{YOUR_NAME}_beats.npy", np.array(collected))
print(f"Saved {len(collected)} beats to {YOUR_NAME}_beats.npy")
