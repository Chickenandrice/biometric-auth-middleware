"""Simulate an authorization flow without a real edge device.

Directly inserts an enrollment embedding and then tests verification
by calling the API with a mock transport.
"""

import asyncio
import numpy as np

from backend.app.db.session import init_db, async_session
from backend.app.db import crud
from backend.app.services.vector_store_service import vector_store
from backend.app.services.scoring_service import scoring_service


def make_embedding(dim: int = 64) -> list[float]:
    """Generate a random unit-norm embedding."""
    vec = np.random.randn(dim)
    vec = vec / np.linalg.norm(vec)
    return vec.tolist()


def add_noise(embedding: list[float], noise_level: float = 0.05) -> list[float]:
    """Add small gaussian noise to simulate a live capture."""
    arr = np.array(embedding)
    noise = np.random.randn(len(arr)) * noise_level
    result = arr + noise
    result = result / np.linalg.norm(result)
    return result.tolist()


async def main():
    await init_db()

    user_id = "alice"
    async with async_session() as db:
        # Ensure user exists
        if not await crud.get_user(db, user_id):
            await crud.create_user(db, user_id, "Alice Chen")

        # Simulate enrollment
        enrolled_emb = make_embedding()
        vector_store.store_embedding(user_id, enrolled_emb)
        await crud.upsert_baseline(db, user_id, bpm_mean=72, bpm_std=6, hrv_mean=42, hrv_std=8)
        await crud.set_user_enrolled(db, user_id, True)
        print(f"[Enrolled] {user_id}")

        # Simulate verification — matching user
        live_emb = add_noise(enrolled_emb, noise_level=0.05)
        baseline = await crud.get_baseline(db, user_id)
        identity_score = scoring_service.compute_identity_score(live_emb, enrolled_emb)
        anomaly_score = scoring_service.compute_anomaly_score(74, 40, baseline)
        print(f"\n[Scenario 1: Normal approval]")
        print(f"  Identity score: {identity_score:.4f}")
        print(f"  Anomaly score:  {anomaly_score:.4f}")
        print(f"  Decision:       {'allow' if identity_score > 0.75 else 'deny'}")

        # Simulate verification — different user (impostor)
        impostor_emb = make_embedding()
        identity_score_2 = scoring_service.compute_identity_score(impostor_emb, enrolled_emb)
        print(f"\n[Scenario 2: Impostor denial]")
        print(f"  Identity score: {identity_score_2:.4f}")
        print(f"  Decision:       {'allow' if identity_score_2 > 0.75 else 'deny'}")

        # Simulate verification — stress/duress
        live_emb_3 = add_noise(enrolled_emb, noise_level=0.08)
        identity_score_3 = scoring_service.compute_identity_score(live_emb_3, enrolled_emb)
        anomaly_score_3 = scoring_service.compute_anomaly_score(120, 18, baseline)
        print(f"\n[Scenario 3: Stress/duress]")
        print(f"  Identity score: {identity_score_3:.4f}")
        print(f"  Anomaly score:  {anomaly_score_3:.4f}")
        print(f"  Decision:       {'deny (anomaly)' if anomaly_score_3 > 2.5 else 'allow'}")


if __name__ == "__main__":
    asyncio.run(main())
