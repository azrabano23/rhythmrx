"""Chronopharmacology model: insulin sensitivity, glucose response, and dose timing.

Given a patient's circadian phase (from `phase.py`), this models when their body is
most able to use a glucose-lowering drug, simulates a day of meals + medication, and
finds the once-daily dose time that minimizes glycemic burden. The mechanism is the
whole RhythmRX thesis: a dose taken when the body is most insulin-sensitive does more
work, so the *right hour* depends on the patient's measured clock — not the clinic's.
"""
from __future__ import annotations

import math

_PERIOD = 24.0
TARGET = 100.0        # mg/dL baseline
HYPER = 140.0         # mg/dL post-meal hyperglycemia threshold

# Hours from the patient's cortisol acrophase to their insulin-sensitivity peak.
# CALIBRATED to real data: on ShanghaiT2DM the empirical sensitivity peak (lowest
# glycemic response per gram of food) is ~10:00; anchored to a typical ~08:00
# cortisol peak that is a +2 h offset. See validation.py.
SENS_PEAK_OFFSET = 2.0


def insulin_sensitivity(hour: float, phase: float) -> float:
    """Insulin sensitivity in [0, 1] at clock `hour` for a patient with this phase.

    Peaks ~2 h after the cortisol acrophase (calibrated to real CGM — see
    `SENS_PEAK_OFFSET`) and troughs in the biological evening — the shape behind the
    documented evening glucose intolerance that this model is *validated against* in
    `validation.py` (r = 0.66 vs. real post-meal excursions). Anchored to the
    patient's phase, so a shifted clock slides the whole curve.
    """
    sens_peak = (phase + SENS_PEAK_OFFSET) % _PERIOD
    return 0.5 * (1.0 + math.cos(2.0 * math.pi * (hour - sens_peak) / _PERIOD))


def meal_excursion(t: float, meal_hour: float, carbs: float,
                   tau: float = 1.2, scale: float = 1.3) -> float:
    """Glucose rise (mg/dL) at time t from a meal of `carbs` grams at meal_hour.

    Normalized gamma kernel peaking `tau` h post-meal at height carbs·scale, with a
    multi-hour tail (a 70 g meal spikes ~+90 mg/dL — a realistic diabetic excursion).
    """
    dt = t - meal_hour
    if dt < 0:
        return 0.0
    return carbs * scale * (dt / tau) * math.exp(1.0 - dt / tau)


def med_clearance(t: float, dose_hour: float, phase: float, potency: float) -> float:
    """Glucose-lowering from a once-daily dose, active ~14 h after dosing.

    Strength scales with insulin sensitivity *at the time the dose is taken* — the
    chronotherapy mechanism in one line."""
    dt = t - dose_hour
    if dt < 0 or dt > 14.0:
        return 0.0
    sens = insulin_sensitivity(dose_hour, phase)
    return potency * sens * math.sin(math.pi * dt / 14.0)


def simulate_day(meals: list[tuple[float, float]], dose_hour: float, phase: float,
                 potency: float = 70.0, step: float = 0.25) -> dict:
    """Simulate one day; return hyperglycemia AUC and time-in-range.

    glucose(t) = baseline + Σ meal excursions − medication clearance (floored).
    """
    t, auc_over, in_range, total = 6.0, 0.0, 0, 0
    while t <= 24.0:
        g = TARGET + sum(meal_excursion(t, mh, c) for mh, c in meals)
        g -= med_clearance(t, dose_hour, phase, potency)
        g = max(TARGET * 0.7, g)
        auc_over += max(0.0, g - HYPER) * step
        total += 1
        in_range += 1 if 70.0 <= g <= HYPER else 0
        t += step
    return {"hyperglycemia_auc": round(auc_over, 1),
            "time_in_range_pct": round(100.0 * in_range / total, 1)}


def optimal_dose_time(phase: float, meals: list[tuple[float, float]],
                      potency: float = 70.0) -> float:
    """Search dose times 06:00–20:00; return the one minimizing hyperglycemia AUC."""
    best_t, best_auc = 6.0, float("inf")
    t = 6.0
    while t <= 20.0:
        auc = simulate_day(meals, t, phase, potency)["hyperglycemia_auc"]
        if auc < best_auc:
            best_auc, best_t = auc, t
        t += 0.5
    return round(best_t, 2)
