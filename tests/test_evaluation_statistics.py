"""SP0011 — statistical machinery (real reference computations)."""
from __future__ import annotations

from tools.evaluation import statistics as st, robust, longhorizon, calibration


def test_clopper_pearson_lower_monotone():
    lo_low = st.clopper_pearson_lower(15, 20)
    lo_high = st.clopper_pearson_lower(19, 20)
    assert 0 < lo_low < lo_high < 1


def test_clopper_pearson_all_success():
    # successes==n uses alpha^(1/n); still < 1
    lb = st.clopper_pearson_lower(20, 20, 0.05)
    assert 0.8 < lb < 1.0


def test_zero_failure_upper_bound_not_zero():
    z = st.zero_failure_upper_bound(200)
    assert z["failure_rate_upper_bound"] > 0        # never zero risk
    assert z["zero_risk_claimed"] is False


def test_e_process_ville():
    strong = st.e_process_bernoulli([1] * 30, 0.5)
    assert strong["max_e"] > 1.0
    assert strong["optional_stopping_valid"] is True


def test_confidence_sequence_time_uniform():
    cs = st.confidence_sequence(80, 100)
    assert cs["time_uniform"] is True and 0 <= cs["lower_bound"] <= cs["p_hat"]


def test_effective_sample_size_deflates():
    e = st.effective_sample_size(100, [10] * 10, icc=0.3)
    assert e["effective_n"] < 100            # correlated runs are not independent


def test_multiple_testing_controls():
    pv = {"a": 0.001, "b": 0.02, "c": 0.9}
    assert st.bonferroni(pv, 0.05)["threshold"] < 0.05
    assert "c" not in st.benjamini_hochberg(pv, 0.05)["rejected"]


def test_equivalence_requires_ci_inside_margin():
    assert st.equivalence(0.0, -0.02, 0.02, 0.05)["equivalent"] is True
    assert st.equivalence(0.0, -0.2, 0.2, 0.05)["equivalent"] is False


def test_worst_stratum_min():
    ws = robust.worst_stratum({"PL": (18, 20), "EN": (10, 20)},
                              {"PL": 0.5, "EN": 0.5})
    assert ws["worst_stratum"] == "EN"
    assert ws["worst_lower_bound"] <= min(0.6, ws["stratum_lower_bounds"]["PL"])


def test_robust_mixture_is_min_over_declared():
    lb = {"PL": 0.9, "EN": 0.5}
    rm = robust.robust_mixture_lower_bound(lb, [{"PL": 1.0}, {"EN": 1.0}])
    assert abs(rm["robust_lower_bound"] - 0.5) < 1e-9   # worst mixture


def test_cvar_is_loss_not_probability():
    c = robust.cvar([0, 0, 1, 0, 1, 0], 0.9)
    assert c["is_probability"] is False and c["cvar"] is not None


def test_horizon_curve_labels_extrapolation():
    hc = longhorizon.horizon_curve([(60, 1), (120, 1), (240, 0), (300, 0)])
    assert hc["p50_region"] in ("INTERPOLATION", "EXTRAPOLATION", "UNDEFINED")


def test_competing_risks_incidence():
    cr = longhorizon.competing_risks(
        [(10, "success"), (20, "timeout"), (30, "tool_failure")], 25)
    assert "timeout" in cr["cumulative_incidence"]
    assert cr["recovery_erases_failure"] is False


def test_brier_and_calibration():
    assert calibration.brier_score([(1.0, 1), (0.0, 0)]) == 0.0
    rc = calibration.reliability_curve([(0.9, 1), (0.9, 0), (0.1, 0)])
    assert "expected_calibration_error" in rc


def test_selective_risk_reports_both():
    sr = calibration.selective_risk([(0.9, 1), (0.5, 0), (0.95, 1)], 0.8)
    assert "coverage" in sr and "selective_risk" in sr


def test_conformal_distribution_free():
    ct = calibration.conformal_threshold([0.1, 0.2, 0.3, 0.4, 0.5], 0.1)
    assert ct["distribution_free"] is True
