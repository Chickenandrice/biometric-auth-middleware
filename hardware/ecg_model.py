import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from sklearn.metrics import roc_curve, accuracy_score

SIGNAL_LEN       = 188
EMBED_DIM        = 128
MARGIN           = 0.5
BATCH_SIZE       = 64
EPOCHS           = 50
LR               = 1e-3
BEATS_PER_PERSON = 500
THRESHOLD        = 0.6
DROPOUT          = 0.3
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

np.random.seed(42)

PERSON_PROFILES = {
    "Varun":    dict(r=1.00, t=0.35, p=0.20, qrs_w=8,  pr=20, t_width=12, st_elev=0.00, noise=0.03),
    "Joey":     dict(r=0.75, t=0.50, p=0.15, qrs_w=12, pr=25, t_width=14, st_elev=0.00, noise=0.05),
    "Kyle":     dict(r=0.90, t=0.20, p=0.25, qrs_w=7,  pr=18, t_width=10, st_elev=0.00, noise=0.02),
    "Raymond":  dict(r=0.55, t=0.15, p=0.35, qrs_w=16, pr=40, t_width=16, st_elev=0.00, noise=0.02),
    "Alex":     dict(r=0.95, t=0.60, p=0.30, qrs_w=6,  pr=35, t_width=18, st_elev=0.05, noise=0.02),
    "Margaret": dict(r=0.65, t=0.10, p=0.12, qrs_w=18, pr=38, t_width=20, st_elev=0.02, noise=0.04),
    "Derek":    dict(r=0.80, t=-0.20, p=0.18, qrs_w=9, pr=22, t_width=11, st_elev=0.00, noise=0.03),
    "Priya":    dict(r=0.85, t=0.45, p=0.22, qrs_w=10, pr=21, t_width=13, st_elev=0.12, noise=0.03),
    "Sam":      dict(r=0.40, t=0.12, p=0.08, qrs_w=11, pr=24, t_width=12, st_elev=0.00, noise=0.07),
    "Lena":     dict(r=0.70, t=0.25, p=0.14, qrs_w=22, pr=20, t_width=15, st_elev=0.00, noise=0.04),
    "Marcus":   dict(r=0.88, t=0.38, p=0.16, qrs_w=8,  pr=10, t_width=11, st_elev=0.00, noise=0.03),
    "Nina":     dict(r=0.60, t=0.70, p=0.20, qrs_w=9,  pr=23, t_width=9,  st_elev=0.00, noise=0.04),
}

person_names = list(PERSON_PROFILES.keys())
id_to_name   = {i: n for i, n in enumerate(person_names)}

def gaussian_bump(length, center, width, amplitude):
    x = np.arange(length)
    return amplitude * np.exp(-0.5 * ((x - center) / width) ** 2)

def generate_beat(profile, signal_len=SIGNAL_LEN, normalize=True):
    beat   = np.zeros(signal_len, dtype=np.float32)
    jitter = lambda std: np.random.normal(0, std)
    r       = profile["r"]       + jitter(0.04)
    t       = profile["t"]       + jitter(0.03)
    p       = profile["p"]       + jitter(0.02)
    qw      = profile["qrs_w"]
    pr      = profile["pr"]      + jitter(2)
    t_width = profile["t_width"] + jitter(1)
    st_elev = profile["st_elev"] + jitter(0.01)
    r_c     = signal_len // 2
    beat += gaussian_bump(signal_len, r_c - pr,       width=6,       amplitude=p)
    beat += gaussian_bump(signal_len, r_c - qw // 2,  width=2,       amplitude=-0.15)
    beat += gaussian_bump(signal_len, r_c,             width=qw // 2, amplitude=r)
    beat += gaussian_bump(signal_len, r_c + qw // 2,  width=2,       amplitude=-0.10)
    beat += gaussian_bump(signal_len, r_c + qw,        width=8,       amplitude=st_elev)
    beat += gaussian_bump(signal_len, r_c + pr + 10,  width=t_width, amplitude=t)
    if profile.get("qrs_w", 0) >= 20:
        beat += gaussian_bump(signal_len, r_c + 6, width=3, amplitude=r * 0.4 + jitter(0.05))
    beat += np.random.normal(0, profile["noise"], signal_len).astype(np.float32)
    if normalize:
        beat = (beat - beat.min()) / (beat.max() - beat.min() + 1e-8)
    return beat

class TripletECGDataset(Dataset):
    def __init__(self, signals, labels):
        self.signals    = torch.tensor(signals).unsqueeze(1)
        self.labels     = labels
        self.person_ids = np.unique(labels)
        self.index      = {p: np.where(labels == p)[0] for p in self.person_ids}

    def __len__(self):
        return len(self.signals)

    def __getitem__(self, idx):
        anchor_label = self.labels[idx]
        anchor       = self.signals[idx]
        pos_idx = idx
        while pos_idx == idx:
            pos_idx = np.random.choice(self.index[anchor_label])
        positive = self.signals[pos_idx]
        neg_label = np.random.choice([p for p in self.person_ids if p != anchor_label])
        neg_idx   = np.random.choice(self.index[neg_label])
        negative  = self.signals[neg_idx]
        return anchor, positive, negative

class ECGEncoder(nn.Module):
    def __init__(self, embed_dim=EMBED_DIM, dropout=DROPOUT):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(1, 32,  kernel_size=5, padding=2),
            nn.BatchNorm1d(32),  nn.ReLU(), nn.MaxPool1d(2), nn.Dropout(dropout),
            nn.Conv1d(32, 64, kernel_size=5, padding=2),
            nn.BatchNorm1d(64),  nn.ReLU(), nn.MaxPool1d(2), nn.Dropout(dropout),
            nn.Conv1d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm1d(128), nn.ReLU(), nn.AdaptiveAvgPool1d(1),
        )
        self.fc = nn.Sequential(
            nn.Flatten(),
            nn.Linear(128, embed_dim),
            nn.BatchNorm1d(embed_dim),
        )

    def forward(self, x):
        return F.normalize(self.fc(self.conv(x)), p=2, dim=1)

class TripletLoss(nn.Module):
    def __init__(self, margin=MARGIN):
        super().__init__()
        self.margin = margin

    def forward(self, anchor, positive, negative):
        d_pos = F.pairwise_distance(anchor, positive)
        d_neg = F.pairwise_distance(anchor, negative)
        return F.relu(d_pos - d_neg + self.margin).mean()
# ════════════════════════════════════════════════════════
#  TRAINING
# ════════════════════════════════════════════════════════
def run_epoch(loader, encoder, criterion, optimizer):
    encoder.train()
    total_loss, n_batches = 0, 0
    for anchor, positive, negative in loader:
        anchor   = anchor.to(DEVICE)
        positive = positive.to(DEVICE)
        negative = negative.to(DEVICE)
        loss = criterion(encoder(anchor), encoder(positive), encoder(negative))
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        total_loss += loss.item()
        n_batches  += 1
    return total_loss / n_batches

# ════════════════════════════════════════════════════════
#  ENROLLMENT
# ════════════════════════════════════════════════════════
def build_gallery(encoder, signals, labels, people, n_templates=10):
    gallery = {}
    encoder.eval()
    with torch.no_grad():
        for person in people:
            idxs   = np.where(labels == person)[0][:n_templates]
            beats  = torch.tensor(signals[idxs]).unsqueeze(1).to(DEVICE)
            embeds = encoder(beats)
            gallery[person] = embeds.mean(dim=0)
    return gallery

# ════════════════════════════════════════════════════════
#  EVALUATION
# ════════════════════════════════════════════════════════
def evaluate(encoder, signals, labels, gallery, threshold=THRESHOLD):
    encoder.eval()
    results = []
    with torch.no_grad():
        beats  = torch.tensor(signals).unsqueeze(1).to(DEVICE)
        embeds = encoder(beats).cpu()
    for embed, true_label in zip(embeds, labels):
        for claimed, ref in gallery.items():
            score = 1 - F.pairwise_distance(
                embed.unsqueeze(0), ref.cpu().unsqueeze(0)
            ).item()
            results.append((int(true_label), claimed, score))

    FA    = sum(1 for t, c, s in results if t != c and s >= threshold)
    FR    = sum(1 for t, c, s in results if t == c and s <  threshold)
    N_imp = sum(1 for t, c, _ in results if t != c)
    N_gen = sum(1 for t, c, _ in results if t == c)
    FAR   = FA / N_imp if N_imp > 0 else 0
    FRR   = FR / N_gen if N_gen > 0 else 0

    y_binary_true = [1 if t == c else 0 for t, c, s in results]
    y_binary_pred = [1 if s >= threshold else 0 for _, _, s in results]
    acc = accuracy_score(y_binary_true, y_binary_pred)

    y_true  = [1 if t == c else 0 for t, c, s in results]
    y_score = [s for _, _, s in results]
    fpr, tpr, thr_roc = roc_curve(y_true, y_score)
    fnr     = 1 - tpr
    eer_idx = np.argmin(np.abs(fpr - fnr))
    EER     = (fpr[eer_idx] + fnr[eer_idx]) / 2

    print("\n" + "=" * 55)
    print("  TEST RESULTS")
    print("=" * 55)
    print(f"  Threshold        : {threshold}")
    print(f"  Overall Accuracy : {acc * 100:.2f}%")
    print(f"  FAR              : {FAR:.4f}  ({FA}/{N_imp} impostors accepted)")
    print(f"  FRR              : {FRR:.4f}  ({FR}/{N_gen} real users rejected)")
    print(f"  EER              : {EER:.4f}  (at threshold {thr_roc[eer_idx]:.4f})")

    print("\n── Per-Person Score Breakdown ──────────────────────")
    print(f"  {'Query':<12} {'Claimed':<12} {'Avg Score':>10}  Decision")
    print("  " + "-" * 52)
    for person in np.unique(labels):
        for claimed in gallery:
            scores = [s for t, c, s in results if t == person and c == claimed]
            if not scores:
                continue
            avg      = np.mean(scores)
            expected = "SAME" if person == claimed else "DIFF"
            decision = "✅ ACCEPT" if avg >= threshold else "❌ REJECT"
            marker   = " ← WRONG" if (expected == "SAME" and avg < threshold) or \
                                      (expected == "DIFF" and avg >= threshold) else ""
            print(f"  {id_to_name[person]:<12} {id_to_name[claimed]:<12} {avg:>10.4f}  {decision}{marker}")

# ════════════════════════════════════════════════════════
#  LIVE VERIFICATION
# ════════════════════════════════════════════════════════
def verify(encoder, signal, claimed_person_id, gallery, threshold=THRESHOLD):
    encoder.eval()
    with torch.no_grad():
        beat  = torch.tensor(signal).unsqueeze(0).unsqueeze(0).to(DEVICE)
        embed = encoder(beat).cpu()
        ref   = gallery[claimed_person_id].cpu()
        score = 1 - F.pairwise_distance(embed, ref.unsqueeze(0)).item()
    name     = id_to_name[claimed_person_id]
    decision = "✅ ACCESS GRANTED" if score >= threshold else "❌ ACCESS DENIED"
    print(f"  Claimed: {name:<12} | Score: {score:.4f} | {decision}")

# ════════════════════════════════════════════════════════
#  UNKNOWN DETECTION
# ════════════════════════════════════════════════════════
def detect_unknown(encoder, signal, gallery, threshold=THRESHOLD, label="?"):
    encoder.eval()
    with torch.no_grad():
        beat  = torch.tensor(signal).unsqueeze(0).unsqueeze(0).to(DEVICE)
        embed = encoder(beat).cpu()
    best_score = max(
        1 - F.pairwise_distance(embed, ref.cpu().unsqueeze(0)).item()
        for ref in gallery.values()
    )
    if best_score >= threshold:
        print(f"  [{label}]  ✅ GRANTED  (score: {best_score:.4f})")
    else:
        print(f"  [{label}]  ❌ UNKNOWN — state not recognized")
