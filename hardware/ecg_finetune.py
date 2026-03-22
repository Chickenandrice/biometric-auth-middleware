import torch
import torch.optim as optim
import numpy as np
from torch.utils.data import DataLoader
from ecg_model import (
    ECGEncoder, TripletECGDataset, TripletLoss,
    run_epoch, build_gallery,
    DEVICE, EMBED_DIM, BATCH_SIZE, THRESHOLD,
    id_to_name
)

# ── Config ────────────────────────────────────────────────
FINETUNE_EPOCHS = 20
FINETUNE_LR     = 1e-4     # Lower than original LR to avoid overwriting learned features

# ── Load real beats ───────────────────────────────────────
# Add as many people as you have .npy files for
# person_id must match the id used during original training
real_data = {
    0: np.load("Varun_beats.npy"),     # person_id 0 = Varun
    1: np.load("Joey_beats.npy"),      # person_id 1 = Joey
    # Add more as you collect them
}

# ── Build real dataset arrays ─────────────────────────────
signals_list, labels_list = [], []
for person_id, beats in real_data.items():
    for beat in beats:
        signals_list.append(beat)
        labels_list.append(person_id)

signals = np.stack(signals_list).astype(np.float32)
labels  = np.array(labels_list)

print(f"Fine-tune samples : {len(signals)}")
print(f"People            : {[id_to_name[p] for p in real_data.keys()]}")

# ── Load pre-trained encoder ──────────────────────────────
encoder = ECGEncoder().to(DEVICE)
encoder.load_state_dict(
    torch.load("best_encoder.pt", map_location=DEVICE, weights_only=True)
)
print("Loaded best_encoder.pt")

# ── Freeze conv layers, only train FC ────────────────────
# Optional: comment this block out to fine-tune the full network
for name, param in encoder.named_parameters():
    if "conv" in name:
        param.requires_grad = False

trainable = sum(p.numel() for p in encoder.parameters() if p.requires_grad)
print(f"Trainable parameters : {trainable:,}")

# ── Fine-tune setup ───────────────────────────────────────
optimizer = optim.Adam(
    filter(lambda p: p.requires_grad, encoder.parameters()),
    lr=FINETUNE_LR,
    weight_decay=1e-4
)
scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=8, gamma=0.5)
criterion = TripletLoss()

loader = DataLoader(
    TripletECGDataset(signals, labels),
    batch_size=min(BATCH_SIZE, len(signals) // 2),
    shuffle=True,
    num_workers=0
)

# ── Fine-tune loop ────────────────────────────────────────
print("\n" + "=" * 45)
print("  FINE-TUNING on real ECG beats")
print("=" * 45)
print(f"{'Epoch':<8} {'Loss':<14} {'Status'}")
print("-" * 32)

best_loss = float("inf")
for epoch in range(1, FINETUNE_EPOCHS + 1):
    loss = run_epoch(loader, encoder, criterion, optimizer)
    scheduler.step()

    status = ""
    if loss < best_loss:
        best_loss = loss
        torch.save(encoder.state_dict(), "finetuned_encoder.pt")
        status = "  ← saved"

    print(f"{epoch:<8} {loss:<14.4f}{status}")

print(f"\nBest fine-tune loss : {best_loss:.4f}")
print("Saved → finetuned_encoder.pt")

# ── Re-enroll with finetuned model ────────────────────────
encoder.load_state_dict(
    torch.load("finetuned_encoder.pt", map_location=DEVICE, weights_only=True)
)

real_gallery = {}
for person_id, beats in real_data.items():
    beats_t = torch.tensor(beats).unsqueeze(1).to(DEVICE)
    with torch.no_grad():
        embeds = encoder(beats_t)
    real_gallery[person_id] = embeds.mean(dim=0)
    print(f"Re-enrolled: {id_to_name[person_id]}")

torch.save(real_gallery, "real_gallery.pt")
print("Saved → real_gallery.pt")
