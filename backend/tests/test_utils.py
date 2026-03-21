"""Tests for utility modules: similarity, thresholds, security."""

import pytest
import numpy as np

from backend.app.utils.similarity import cosine_similarity
from backend.app.utils.thresholds import get_identity_threshold, get_anomaly_threshold


# ── Cosine similarity ──

class TestCosineSimilarity:
    def test_identical_vectors(self):
        vec = [1.0, 0.0, 0.0]
        assert cosine_similarity(vec, vec) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_similar_vectors_high_score(self):
        rng = np.random.default_rng(0)
        base = rng.standard_normal(64)
        base = base / np.linalg.norm(base)
        noisy = base + rng.standard_normal(64) * 0.05
        noisy = noisy / np.linalg.norm(noisy)
        score = cosine_similarity(base.tolist(), noisy.tolist())
        assert score > 0.9

    def test_random_vectors_low_score(self):
        rng = np.random.default_rng(0)
        a = rng.standard_normal(64).tolist()
        b = rng.standard_normal(64).tolist()
        # Random 64-d vectors have near-zero cosine similarity
        score = cosine_similarity(a, b)
        assert abs(score) < 0.5

    def test_zero_vector_returns_zero(self):
        assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0

    def test_both_zero_vectors(self):
        assert cosine_similarity([0.0], [0.0]) == 0.0

    def test_single_dimension(self):
        assert cosine_similarity([3.0], [5.0]) == pytest.approx(1.0)

    def test_high_dimensional(self):
        rng = np.random.default_rng(7)
        vec = rng.standard_normal(512)
        vec = vec / np.linalg.norm(vec)
        assert cosine_similarity(vec.tolist(), vec.tolist()) == pytest.approx(1.0, abs=1e-10)


# ── Thresholds ──

class TestThresholds:
    def test_low_risk_identity_threshold_is_zero(self):
        assert get_identity_threshold("low") == 0.0

    def test_high_risk_identity_threshold(self):
        assert get_identity_threshold("high") == 0.75

    def test_critical_risk_identity_threshold_higher_than_high(self):
        assert get_identity_threshold("critical") > get_identity_threshold("high")

    def test_policy_override_identity(self):
        assert get_identity_threshold("high", policy_override=0.9) == 0.9

    def test_policy_override_zero_is_respected(self):
        assert get_identity_threshold("critical", policy_override=0.0) == 0.0

    def test_unknown_risk_level_uses_default(self):
        assert get_identity_threshold("unknown") == 0.75

    def test_low_risk_anomaly_threshold_very_high(self):
        assert get_anomaly_threshold("low") == 999.0

    def test_critical_anomaly_threshold_stricter_than_high(self):
        assert get_anomaly_threshold("critical") < get_anomaly_threshold("high")

    def test_policy_override_anomaly(self):
        assert get_anomaly_threshold("high", policy_override=1.5) == 1.5
