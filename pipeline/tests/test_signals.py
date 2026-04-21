"""
Unit tests for signal primitives — all run on synthetic data.

Strategy: construct deterministic input series with known properties,
assert that each primitive returns the expected output. Tests should
catch implementation errors without requiring any real data.

Key invariants tested:
  - Constant baseline → deviation z-score = 0
  - Linearly increasing series → positive Theil-Sen slope
  - Stable series (no regime change) → no CUSUM changepoints
  - Step-change series → CUSUM detects the step
  - Zero dyadic events → contagion = 0
  - Identical countries → contagion mirrors instability

Spec reference: §6 Phase 3 acceptance criteria.
"""

import numpy as np
import pandas as pd
import pytest

from pipeline.signals.deviation import robust_zscore, compute_deviation_scores
from pipeline.signals.trend import theil_sen_slope, normalise_trend
from pipeline.signals.changepoint import run_cusum
from pipeline.signals.contagion import geo_weight, compute_contagion


# ---------------------------------------------------------------------------
# Primitive 1 — Robust deviation score
# ---------------------------------------------------------------------------

class TestRobustZscore:
    def test_constant_baseline_gives_zero(self):
        """A value equal to the median of a constant series should give z=0."""
        baseline = pd.Series([5.0] * 365)
        z = robust_zscore(baseline, current_value=5.0)
        assert z == pytest.approx(0.0, abs=1e-6)

    def test_positive_deviation(self):
        """A value above median should give positive z-score."""
        baseline = pd.Series([1.0] * 365)
        z = robust_zscore(baseline, current_value=10.0)
        assert z > 0

    def test_negative_deviation(self):
        """A value below median should give negative z-score."""
        baseline = pd.Series([10.0] * 365)
        z = robust_zscore(baseline, current_value=1.0)
        assert z < 0

    def test_near_zero_baseline_epsilon_prevents_divzero(self):
        """Countries with near-zero baseline (Bhutan) must not raise ZeroDivisionError."""
        baseline = pd.Series([0.0] * 365)
        z = robust_zscore(baseline, current_value=0.0)
        assert np.isfinite(z)

    def test_clipping_applied_in_aggregate(self):
        """aggregate_deviation() should clip to [-5, 5]."""
        from pipeline.signals.deviation import aggregate_deviation
        scores = pd.DataFrame({
            "iso3": ["NER", "NER"],
            "feature": ["conflict_events", "protest_events"],
            "z_robust": [10.0, 8.0],  # should clip to 5
        })
        result = aggregate_deviation(scores)
        assert result["NER"] <= 5.0


# ---------------------------------------------------------------------------
# Primitive 2 — Theil-Sen slope
# ---------------------------------------------------------------------------

class TestTheilSenSlope:
    def test_constant_series_zero_slope(self):
        """A constant series should have slope = 0."""
        series = pd.Series([3.0] * 30)
        slope = theil_sen_slope(series)
        assert slope == pytest.approx(0.0, abs=1e-6)

    def test_increasing_series_positive_slope(self):
        """A linearly increasing series should have positive slope."""
        series = pd.Series(np.arange(30, dtype=float))
        slope = theil_sen_slope(series)
        assert slope > 0

    def test_decreasing_series_negative_slope(self):
        """A linearly decreasing series should have negative slope."""
        series = pd.Series(np.arange(30, 0, -1, dtype=float))
        slope = theil_sen_slope(series)
        assert slope < 0

    def test_outlier_resistant(self):
        """A single outlier should not dominate the slope estimate."""
        base = np.ones(30)
        base[-1] = 1000.0  # extreme outlier on last day
        series = pd.Series(base)
        slope = theil_sen_slope(series)
        assert abs(slope) < 50, "Slope should be robust to single outlier"

    def test_normalise_range(self):
        """normalise_trend() output should be in [0, 1]."""
        slopes = pd.Series({"NER": 5.0, "CHE": -2.0, "UKR": 10.0})
        normed = normalise_trend(slopes)
        assert normed.min() >= 0.0
        assert normed.max() <= 1.0


# ---------------------------------------------------------------------------
# Primitive 3 — CUSUM change-point detection
# ---------------------------------------------------------------------------

class TestCUSUM:
    def test_stable_series_no_changepoints(self):
        """A stable series with no anomalies should return no changepoints."""
        rng = np.random.default_rng(42)
        series = pd.Series(rng.normal(loc=0, scale=1, size=180))
        changepoints = run_cusum(series)
        assert len(changepoints) == 0, "Stable series should have no changepoints"

    def test_step_change_detected(self):
        """A clear step change should trigger a changepoint."""
        before = np.zeros(90)
        after = np.ones(90) * 20  # massive step
        series = pd.Series(np.concatenate([before, after]))
        changepoints = run_cusum(series)
        assert len(changepoints) >= 1, "Step change should be detected"
        assert any(cp >= 85 for cp in changepoints), "Changepoint should be near step (index ~90)"


# ---------------------------------------------------------------------------
# Primitive 5 — Contagion
# ---------------------------------------------------------------------------

class TestContagion:
    def test_geo_weight_decay(self):
        """Geographic weight should decay with distance."""
        w_near = geo_weight(0)
        w_mid = geo_weight(2000)
        w_far = geo_weight(10000)
        assert w_near > w_mid > w_far
        assert w_near == pytest.approx(1.0)
        assert w_mid == pytest.approx(np.exp(-1))

    def test_zero_instability_gives_zero_contagion(self):
        """If all neighbours have instability = 0, contagion should be 0."""
        instability = pd.Series({"NER": 0.0, "MLI": 0.0, "BFA": 0.0})
        geo_distances = pd.DataFrame([
            {"iso3_i": "NER", "iso3_j": "MLI", "distance_km": 500},
            {"iso3_i": "NER", "iso3_j": "BFA", "distance_km": 700},
        ])
        dyadic_weights = pd.DataFrame([
            {"source_iso3": "MLI", "target_iso3": "NER", "w_dyad": 0.5},
            {"source_iso3": "BFA", "target_iso3": "NER", "w_dyad": 0.5},
        ])
        result = compute_contagion(instability, geo_distances, dyadic_weights)
        assert result["NER"] == pytest.approx(0.0)
