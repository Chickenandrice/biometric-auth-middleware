import torch
import numpy as np
import torch.nn.functional as F
from ecg_model import ECGEncoder, DEVICE, id_to_name
from ecg_window import *

THRESHOLD = 0.6

encoder = ECGEncoder().to(DEVICE)
encoder.load_state_dict(torch.load("finetuned_encoder.pt", map_location=DEVICE, weights_only=True))
encoder.eval()

real_gallery = torch.load("real_gallery.pt", map_location=DEVICE)

CLAIMED_ID = 0   # Change to the person_id claiming identity

print(f"Live auth as: {id_to_name[CLAIMED_ID]}")
print("Place finger on electrodes...")

with smbus2.SMBus(1) as bus:
    ads_init(bus)
    try:
        while True:
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

                beat = torch.tensor(window).unsqueeze(0).unsqueeze(0).to(DEVICE)
                with torch.no_grad():
                    embed = encoder(beat).cpu()
                    ref   = real_gallery[CLAIMED_ID].cpu()
                    score = 1 - F.pairwise_distance(embed, ref.unsqueeze(0)).item()

                decision = "✅ GRANTED" if score >= THRESHOLD else "❌ DENIED"
                print(f"Score: {score:.4f} | {decision}")

            time.sleep(1.0 / FS)

    except KeyboardInterrupt:
        print("Stopped.")
