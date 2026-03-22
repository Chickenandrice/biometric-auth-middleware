import threading
import time
import numpy as np
import torch
import torch.nn.functional as F
import smbus2
import struct
from flask import Flask, jsonify, request
from collections import deque
from gpiozero import DigitalInputDevice
from scipy.signal import find_peaks

from ecg_model import ECGEncoder, DEVICE, THRESHOLD, id_to_name, SIGNAL_LEN

# ── Flask app ─────────────────────────────────────────────
app = Flask(__name__)

# ── Hardware setup ────────────────────────────────────────
ADS1115_ADDR         = 0x48
REG_CONVERSION       = 0x00
REG_CONFIG           = 0x01
CONFIG_CONTINUOUS_A0 = [0xC3, 0xE3]
FS                   = 860
BUFFER_LEN           = FS * 5

LO_PLUS  = DigitalInputDevice(17)
LO_MINUS = DigitalInputDevice(27)

def ads_init(bus):
    bus.write_i2c_block_data(ADS1115_ADDR, REG_CONFIG, CONFIG_CONTINUOUS_A0)
    time.sleep(0.01)

def ads_read(bus):
    raw   = bus.read_i2c_block_data(ADS1115_ADDR, REG_CONVERSION, 2)
    value = struct.unpack('>h', bytes(raw))[0]
    return value * 4.096 / 32767.0

# ── Signal processing ─────────────────────────────────────
def preprocess(sig):
    x = np.asarray(sig, dtype=np.float32)
    x = x - np.mean(x)
    x = x - np.convolve(x, np.ones(25) / 25, mode='same')
    x = (x - x.min()) / (x.max() - x.min() + 1e-8)
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
    peaks, _ = find_peaks(x, distance=int(0.25 * FS), prominence=0.05)
    return peaks

def collect_beats(n_beats=100):
    collected     = []
    last_peak_idx = -9999
    buffer        = deque(maxlen=BUFFER_LEN)
    sample_count  = 0  # FIX 3: track samples for periodic peak detection

    with smbus2.SMBus(1) as bus:
        ads_init(bus)
        while len(collected) < n_beats:
            if LO_PLUS.value or LO_MINUS.value:
                time.sleep(0.01)
                continue

            buffer.append(ads_read(bus))
            sample_count += 1

            # FIX 3: removed time.sleep(1.0 / FS) — continuous mode ADC self-paces
            # FIX 2: only run expensive peak detection every 200 samples (~232ms at 860 SPS)
            if len(buffer) < BUFFER_LEN or sample_count % 200 != 0:
                continue

            signal = np.array(buffer, dtype=np.float32)
            peaks  = detect_r_peaks(signal)

            for peak in peaks:
                if peak - last_peak_idx < int(0.3 * FS):
                    continue
                window = extract_window(signal, peak)
                if window is None:
                    continue
                last_peak_idx = peak
                collected.append(window)

    return np.array(collected, dtype=np.float32)

# ── Model and gallery state ───────────────────────────────
encoder      = ECGEncoder().to(DEVICE)
# FIX 4: lock to guard real_gallery from concurrent read/write
gallery_lock = threading.Lock()
real_gallery = {}

try:
    encoder.load_state_dict(
        torch.load("finetuned_encoder.pt", map_location=DEVICE, weights_only=True)
    )
    print("Loaded finetuned_encoder.pt")
except FileNotFoundError:
    encoder.load_state_dict(
        torch.load("best_encoder.pt", map_location=DEVICE, weights_only=True)
    )
    print("Loaded best_encoder.pt (no fine-tuned model found)")

try:
    real_gallery = torch.load("real_gallery.pt", map_location=DEVICE)
    print(f"Loaded gallery with {len(real_gallery)} enrolled users")
except FileNotFoundError:
    print("No real_gallery.pt found — enroll users first")

encoder.eval()

# ── Enrollment state tracking ─────────────────────────────
enrollment_status = {"running": False, "message": ""}

# ════════════════════════════════════════════════════════
#  ENDPOINT 1: /enroll
#  POST body: { "user_id": "varun_01", "name": "Varun", "n_beats": 100 }
# ════════════════════════════════════════════════════════
@app.route("/enroll", methods=["POST"])
def enroll():
    global real_gallery, enrollment_status

    if enrollment_status["running"]:
        return jsonify({"status": "error", "message": "Enrollment already in progress"}), 409

    data    = request.get_json()
    # FIX 5: accept user_id (str) to match FastAPI middleware schema
    user_id = str(data.get("user_id", ""))
    name    = data.get("name", user_id)
    n_beats = int(data.get("n_beats", 100))

    if not user_id:
        return jsonify({"status": "error", "message": "user_id is required"}), 400

    def run_enrollment():
        global real_gallery
        enrollment_status["running"] = True
        enrollment_status["message"] = f"Collecting {n_beats} beats for {name}..."

        try:
            beats = collect_beats(n_beats=n_beats)
            np.save(f"{name}_beats.npy", beats)

            beats_t = torch.tensor(beats).unsqueeze(1).to(DEVICE)
            with torch.no_grad():
                embeds = encoder(beats_t)

            # FIX 4: lock gallery write
            with gallery_lock:
                real_gallery[user_id] = embeds.mean(dim=0)
                torch.save(real_gallery, "real_gallery.pt")

            enrollment_status["message"] = f"Enrolled {name} successfully ({len(beats)} beats)"
        except Exception as e:
            enrollment_status["message"] = f"Enrollment failed: {str(e)}"
        finally:
            enrollment_status["running"] = False

    threading.Thread(target=run_enrollment, daemon=True).start()

    return jsonify({
        "status":  "started",
        "message": f"Enrollment started for {name} (user_id={user_id})"
    }), 202


@app.route("/enroll/status", methods=["GET"])
def enroll_status():
    return jsonify(enrollment_status)


# ════════════════════════════════════════════════════════
#  ENDPOINT 2: /authorize
#  POST body: {
#    "user_id": "varun_01",
#    "action": "door_unlock",
#    "risk_level": "high",
#    "n_beats": 5
#  }
# ════════════════════════════════════════════════════════
@app.route("/authorize", methods=["POST"])
def authorize():
    # FIX 4: lock gallery read before checking emptiness
    with gallery_lock:
        gallery_empty = len(real_gallery) == 0

    if gallery_empty:
        return jsonify({"status": "error", "message": "No users enrolled yet"}), 400

    data       = request.get_json()
    # FIX 5: accept user_id (str), action, and risk_level to match FastAPI middleware
    user_id    = str(data.get("user_id", ""))
    action     = data.get("action", "unknown")
    risk_level = data.get("risk_level", "high")
    n_beats    = int(data.get("n_beats", 5))

    if not user_id:
        return jsonify({"status": "error", "message": "user_id is required"}), 400

    # FIX 4: lock gallery read
    with gallery_lock:
        if user_id not in real_gallery:
            return jsonify({
                "status":  "denied",
                "message": f"user_id '{user_id}' not enrolled"
            }), 404
        ref = real_gallery[user_id].cpu()

    try:
        beats   = collect_beats(n_beats=n_beats)
        beats_t = torch.tensor(beats).unsqueeze(1).to(DEVICE)

        with torch.no_grad():
            embeds = encoder(beats_t).cpu()
            # FIX 1: use cosine_similarity — bounded [-1, 1], consistent with THRESHOLD
            scores = [
                F.cosine_similarity(e.unsqueeze(0), ref.unsqueeze(0)).item()
                for e in embeds
            ]

        avg_score = float(np.mean(scores))
        granted   = avg_score >= THRESHOLD
        name      = id_to_name.get(user_id, user_id)

        return jsonify({
            "status":     "granted" if granted else "denied",
            "user_id":    user_id,
            "name":       name,
            "action":     action,
            "risk_level": risk_level,
            "score":      round(avg_score, 4),
            "threshold":  THRESHOLD,
            "message":    "✅ Access granted" if granted else "❌ Access denied"
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ── Run server ────────────────────────────────────────────
if __name__ == "__main__":
    # FIX 6: threaded=True so /authorize's blocking collect_beats()
    # doesn't stall concurrent requests (e.g., /enroll/status polling)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
