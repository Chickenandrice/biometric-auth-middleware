import math

from backend.app.db.models import Baseline
from backend.app.utils.similarity import cosine_similarity


class ScoringService:
    """Computes identity similarity and anomaly scores."""

    def compute_identity_score(
        self, live_embedding: list[float], enrolled_embedding: list[float]
    ) -> float:
        """Cosine similarity between live and enrolled ECG embeddings. Returns [0, 1]."""
        score = cosine_similarity(live_embedding, enrolled_embedding)
        # Clamp to [0, 1] since cosine can technically go negative
        return max(0.0, min(1.0, score))

    def compute_anomaly_score(
        self, bpm: float, hrv: float, baseline: Baseline
    ) -> float:
        """Compute an anomaly z-score from deviation against the user's baseline.

        Returns a combined z-score (higher = more anomalous).
        A score > ~2.5 suggests unusual physiological state (stress, duress, spoofing).
        """
        bpm_z = self._z_score(bpm, baseline.bpm_mean, baseline.bpm_std)
        hrv_z = self._z_score(hrv, baseline.hrv_mean, baseline.hrv_std)
        # Combined score: RMS of individual z-scores
        return math.sqrt((bpm_z ** 2 + hrv_z ** 2) / 2)

    @staticmethod
    def _z_score(value: float, mean: float, std: float) -> float:
        if std <= 0:
            return 0.0 if value == mean else 3.0
        return abs(value - mean) / std


scoring_service = ScoringService()
