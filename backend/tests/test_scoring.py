"""Tests for the scoring service."""

import math
import pytest
import numpy as np
from unittest.mock import MagicMock

from backend.app.services.scoring_service import ScoringService


@pytest.fixture
def scorer():
    return ScoringService()


def _unit_vector(dim=64, seed=42):
    rng = np.random.default_rng(seed)
    vec = rng.standard_normal(dim)
    return (vec / np.linalg.norm(vec)).tolist()


def _make_baseline(bpm_mean=72.0, bpm_std=6.0, hrv_mean=42.0, hrv_std=8.0):
    b = MagicMock()
    b.bpm_mean = bpm_mean
    b.bpm_std = bpm_std
    b.hrv_mean = hrv_mean
    b.hrv_std = hrv_std
    return b


# ── Identity score ──

class TestIdentityScore:
    def test_identical_embeddings_score_one(self, scorer):
        emb = _unit_vector()
        assert scorer.compute_identity_score(emb, emb) == pytest.approx(1.0)

    def test_similar_embeddings_high_score(self, scorer):
        base = np.array(_unit_vector(seed=0))
        noisy = base + np.random.default_rng(1).standard_normal(64) * 0.05
        noisy = (noisy / np.linalg.norm(noisy)).tolist()
        score = scorer.compute_identity_score(noisy, base.tolist())
        assert score > 0.9

    def test_random_embeddings_low_score(self, scorer):
        a = _unit_vector(seed=0)
        b = _unit_vector(seed=99)
        score = scorer.compute_identity_score(a, b)
        assert score < 0.5

    def test_score_clamped_to_zero_one(self, scorer):
        # Opposite vectors would give negative cosine — should clamp to 0
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        score = scorer.compute_identity_score(a, b)
        assert score == 0.0

    def test_zero_vector_returns_zero(self, scorer):
        assert scorer.compute_identity_score([0.0, 0.0], [1.0, 0.0]) == 0.0


# ── Anomaly score ──

class TestAnomalyScore:
    def test_normal_vitals_low_anomaly(self, scorer):
        baseline = _make_baseline()
        score = scorer.compute_anomaly_score(72.0, 42.0, baseline)
        assert score == pytest.approx(0.0)

    def test_slight_deviation_moderate_anomaly(self, scorer):
        baseline = _make_baseline()
        # 1 std dev off on BPM
        score = scorer.compute_anomaly_score(78.0, 42.0, baseline)
        assert 0.5 < score < 1.5

    def test_large_deviation_high_anomaly(self, scorer):
        baseline = _make_baseline()
        # BPM = 120 is 8 std devs off, HRV = 18 is 3 std devs off
        score = scorer.compute_anomaly_score(120.0, 18.0, baseline)
        assert score > 2.5

    def test_zero_std_same_value(self, scorer):
        baseline = _make_baseline(bpm_std=0.0, hrv_std=0.0)
        score = scorer.compute_anomaly_score(72.0, 42.0, baseline)
        assert score == pytest.approx(0.0)

    def test_zero_std_different_value(self, scorer):
        baseline = _make_baseline(bpm_std=0.0, hrv_std=0.0)
        score = scorer.compute_anomaly_score(80.0, 50.0, baseline)
        # Both z-scores should be 3.0, RMS = 3.0
        assert score == pytest.approx(3.0)

    def test_anomaly_is_symmetric(self, scorer):
        baseline = _make_baseline()
        # Above and below mean should give same score
        score_above = scorer.compute_anomaly_score(84.0, 42.0, baseline)
        score_below = scorer.compute_anomaly_score(60.0, 42.0, baseline)
        assert score_above == pytest.approx(score_below)


# ── Z-score helper ──

class TestZScore:
    def test_z_score_basic(self):
        assert ScoringService._z_score(80.0, 72.0, 4.0) == pytest.approx(2.0)

    def test_z_score_negative_deviation(self):
        # Should return absolute value
        assert ScoringService._z_score(64.0, 72.0, 4.0) == pytest.approx(2.0)

    def test_z_score_zero_std_match(self):
        assert ScoringService._z_score(72.0, 72.0, 0.0) == 0.0

    def test_z_score_zero_std_mismatch(self):
        assert ScoringService._z_score(80.0, 72.0, 0.0) == 3.0

    def test_z_score_negative_std(self):
        assert ScoringService._z_score(80.0, 72.0, -1.0) == 3.0
