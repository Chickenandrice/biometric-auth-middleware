from ecg_model import *

if __name__ == '__main__':

    # ── Generate RESTING dataset ──────────────────────────
    signals_list, labels_list = [], []
    for person_id, name in enumerate(person_names):
        for _ in range(BEATS_PER_PERSON):
            signals_list.append(generate_beat(PERSON_PROFILES[name], normalize=True))
            labels_list.append(person_id)

    signals = np.stack(signals_list)
    labels  = np.array(labels_list)

    print("=" * 55)
    print("  ECG SIAMESE NETWORK — EKG 2FA DEMO")
    print("  Training: RESTING data only")
    print("=" * 55)
    print(f"Total resting samples : {signals.shape[0]}")
    print(f"People                : {', '.join(person_names)}")
    print(f"Device                : {DEVICE}")

    # ── Train on 8, enroll all 12 ─────────────────────────
    train_people = list(range(8))
    all_people   = list(range(12))

    def get_subset(signals, labels, people):
        mask = np.isin(labels, people)
        return signals[mask], labels[mask]

    X_train, y_train = get_subset(signals, labels, train_people)
    print(f"\nTraining on : {[id_to_name[p] for p in train_people]}")
    print(f"Enrolling   : all 12 people (resting beats only)")

    train_loader = DataLoader(
        TripletECGDataset(X_train, y_train),
        batch_size=BATCH_SIZE, shuffle=True, num_workers=0
    )

    # ── Model ─────────────────────────────────────────────
    encoder   = ECGEncoder().to(DEVICE)
    optimizer = torch.optim.Adam(encoder.parameters(), lr=LR, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=15, gamma=0.5)
    criterion = TripletLoss()

    print(f"Encoder parameters : {sum(p.numel() for p in encoder.parameters()):,}")

    # ── Training ──────────────────────────────────────────
    print("\n" + "=" * 55)
    print("  TRAINING  (resting ECG only)")
    print("=" * 55)
    print(f"{'Epoch':<8} {'Train Loss':<14} {'Status'}")
    print("-" * 36)

    best_loss = float("inf")
    for epoch in range(1, EPOCHS + 1):
        train_loss = run_epoch(train_loader, encoder, criterion, optimizer)
        scheduler.step()

        status = ""
        if train_loss < best_loss:
            best_loss = train_loss
            torch.save(encoder.state_dict(), "best_encoder.pt")
            status = "  ← saved"

        if epoch % 5 == 0:
            print(f"{epoch:<8} {train_loss:<14.4f}{status}")

    print(f"\nBest loss : {best_loss:.4f}  (saved to best_encoder.pt)")
    encoder.load_state_dict(torch.load("best_encoder.pt", weights_only=True))

    # ── Enrollment ────────────────────────────────────────
    gallery = build_gallery(encoder, signals, labels, all_people, n_templates=10)

    print("\n" + "=" * 55)
    print("  ENROLLMENT  (resting state only)")
    print("=" * 55)
    for p in gallery:
        print(f"  Enrolled: {id_to_name[p]}")

    # ── Test on held-out resting beats ────────────────────
    def get_test_remainder(signals, labels, people, skip=10):
        sigs_out, labels_out = [], []
        for person in people:
            idxs = np.where(labels == person)[0][skip:]
            sigs_out.append(signals[idxs])
            labels_out.append(labels[idxs])
        return np.concatenate(sigs_out), np.concatenate(labels_out)

    X_test, y_test = get_test_remainder(signals, labels, all_people, skip=10)
    evaluate(encoder, X_test, y_test, gallery, threshold=THRESHOLD)

    # ── Live Auth Demo ─────────────────────────────────────
    print("\n" + "=" * 55)
    print("  LIVE AUTH DEMO — Resting State")
    print("=" * 55)
    print("  (Varun resting — should pass)")
    verify(encoder, generate_beat(PERSON_PROFILES["Varun"],   normalize=True), 0, gallery)
    print("  (Joey resting — should pass)")
    verify(encoder, generate_beat(PERSON_PROFILES["Joey"],    normalize=True), 1, gallery)
    print("  (Raymond tries to be Varun — should fail)")
    verify(encoder, generate_beat(PERSON_PROFILES["Raymond"], normalize=True), 0, gallery)
    print("  (Nina tries to be Kyle — should fail)")
    verify(encoder, generate_beat(PERSON_PROFILES["Nina"],    normalize=True), 2, gallery)

    # ── Altered State Detection ────────────────────────────
    SPECIAL_PROFILES = {
        "Varun_sleeping": dict(r=0.55, t=0.75, p=0.12, qrs_w=11, pr=55, t_width=30, st_elev=0.00, noise=0.005),
        "Varun_exercise": dict(r=1.60, t=0.03, p=0.45, qrs_w=15, pr=6,  t_width=4,  st_elev=-0.12, noise=0.25),
        "Varun_stressed": dict(r=1.08, t=0.07, p=0.42, qrs_w=9,  pr=9,  t_width=6,  st_elev=0.06, noise=0.16),
    }

    print("\n" + "=" * 55)
    print("  ALTERED STATE DETECTION")
    print("=" * 55)
    detect_unknown(encoder, generate_beat(SPECIAL_PROFILES["Varun_sleeping"], normalize=False), gallery, label="Varun sleeping    ")
    detect_unknown(encoder, generate_beat(SPECIAL_PROFILES["Varun_exercise"], normalize=False), gallery, label="Varun post-exercise")
    detect_unknown(encoder, generate_beat(SPECIAL_PROFILES["Varun_stressed"], normalize=False), gallery, label="Varun stressed    ")

    print()
    detect_unknown(encoder, generate_beat(PERSON_PROFILES["Varun"], normalize=True), gallery, label="Varun resting ✅  ")
