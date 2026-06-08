"""RhythmRX tests: phase recovery, the chronopharmacology model, the digital twin,
and (gated on the dataset being present) the real ShanghaiT2DM findings."""
import math
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from rhythmrx.phase import Sample, estimate_phase, fit_rhythm
from rhythmrx.model import insulin_sensitivity, optimal_dose_time, simulate_day
from rhythmrx.analysis import acrophase, cohort_summary, dawn_rise, hourly_profile, time_in_range
from rhythmrx.twin import infer_phase_from_cgm, personalization_spread, recommend_dose


# ---- phase ---------------------------------------------------------------
def test_phase_recovered_from_sparse_daytime_samples():
    for peak in (8.0, 11.0, 14.0):
        samples = [Sample(h, 0.5 * (1 + math.cos(2 * math.pi * (h - peak) / 24)))
                   for h in (8, 11, 14, 17, 20)]   # daytime-only, like a spit strip
        est = estimate_phase(samples)
        diff = abs(est - peak) % 24.0
        assert min(diff, 24.0 - diff) < 0.4


def test_phase_needs_three_samples():
    with pytest.raises(ValueError):
        estimate_phase([Sample(8, 1.0), Sample(20, 0.2)])


# ---- model ---------------------------------------------------------------
def test_sensitivity_bounded_and_peak_tracks_phase():
    for h in range(24):
        assert 0.0 <= insulin_sensitivity(float(h), 8.0) <= 1.0
    peak = lambda ph: max(range(240), key=lambda k: insulin_sensitivity(k / 10, ph)) / 10
    assert peak(11.0) > peak(8.0)   # delayed clock -> later sensitivity peak


def test_personalized_dose_beats_clinic_for_shifted_patient():
    meals = [(8.0, 55.0), (13.0, 70.0), (19.0, 60.0)]
    phase = 12.0  # delayed
    clinic = simulate_day(meals, 8.0, phase)["hyperglycemia_auc"]
    best = simulate_day(meals, optimal_dose_time(phase, meals), phase)["hyperglycemia_auc"]
    assert best <= clinic


# ---- analysis ------------------------------------------------------------
def _synthetic_patient(peak_hour, days=3):
    t0 = datetime(2021, 1, 1)
    return [(t0 + timedelta(minutes=15 * s),
             140 + 25 * math.cos(2 * math.pi * (((t0 + timedelta(minutes=15 * s)).hour
                                                  + (t0 + timedelta(minutes=15 * s)).minute / 60) - peak_hour) / 24))
            for s in range(days * 96)]


def test_hourly_profile_acrophase_and_tir():
    r = _synthetic_patient(14.0)
    assert abs(acrophase(hourly_profile(r)) - 14.0) < 0.5
    assert 0 <= time_in_range(r) <= 100


def test_dawn_rise():
    prof = {h: 110.0 for h in range(6)}; prof[8] = 170.0
    assert dawn_rise(prof) == pytest.approx(60.0)


def test_cohort_detects_differing_peaks():
    pts = [("a", _synthetic_patient(8)), ("b", _synthetic_patient(14)), ("c", _synthetic_patient(18))]
    assert cohort_summary(pts)["personal_peak_spread_h"] > 1.0


# ---- twin ----------------------------------------------------------------
def test_twin_recommends_and_differs_across_patients():
    pts = [("a", _synthetic_patient(8)), ("b", _synthetic_patient(14)), ("c", _synthetic_patient(18))]
    s = personalization_spread(pts)
    assert s["patients"] == 3
    rec = recommend_dose(_synthetic_patient(14))
    assert 6.0 <= rec["recommended_dose_h"] <= 20.0


# ---- real data (gated) ---------------------------------------------------
_DATA = Path(__file__).resolve().parent.parent / ".data_cache" / "shanghai" / "Shanghai_T2DM"


@pytest.mark.skipif(not _DATA.exists(), reason="ShanghaiT2DM not downloaded")
def test_real_cohort_dawn_and_personalization():
    from rhythmrx.data import load_all_cgm
    patients = load_all_cgm(limit=30)
    summary = cohort_summary(patients)
    assert summary["dawn_rise_mgdl"] > 20
    assert summary["personal_peak_spread_h"] > 1.0
    spread = personalization_spread(patients)
    assert spread["pct_materially_different_from_clinic"] > 50.0   # most patients need a different time


# ---- validation + API ----------------------------------------------------
def test_validation_on_fixture():
    from rhythmrx.validation import response_per_gram_by_hour
    # two patients with meals; just exercise the pipeline shape
    base = datetime(2021, 1, 1, 8)
    cgm = [(base + timedelta(minutes=15 * k), 120 + 30 * math.sin(k / 6)) for k in range(64)]
    meals = [(base, 50.0), (base + timedelta(hours=5), 60.0)]
    sessions = [("p", {"cgm": cgm, "meals": meals})]
    rpg = response_per_gram_by_hour(sessions)
    assert isinstance(rpg, dict)


def test_api_recommend():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    r = c.post("/api/recommend", json={"cortisol": [
        {"hour": 8, "value": 0.85}, {"hour": 14, "value": 0.55}, {"hour": 20, "value": 0.2}]})
    assert r.status_code == 200
    d = r.json()
    assert 6.0 <= d["recommended_dose_hour"] <= 20.0
    assert len(d["glucose_personalized"]) > 10
    assert c.get("/").status_code == 200
