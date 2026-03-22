import torch
import numpy as np
from ecg_model import ECGEncoder, DEVICE

encoder = ECGEncoder().to(DEVICE)
encoder.load_state_dict(torch.load("best_encoder.pt", map_location=DEVICE, weights_only=True))
encoder.eval()

real_gallery = {}

# Add each person's real beats here
people = {
    "Varun": 0,    # name → person_id used during training
}

for name, person_id in people.items():
    beats = np.load(f"{name}_beats.npy")
    beats_t = torch.tensor(beats).unsqueeze(1).to(DEVICE)  # (N, 1, 188)
    with torch.no_grad():
        embeds = encoder(beats_t)
    real_gallery[person_id] = embeds.mean(dim=0)
    print(f"Enrolled {name} with {len(beats)} real beats")

torch.save(real_gallery, "real_gallery.pt")
print("Saved real_gallery.pt")
