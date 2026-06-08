"""Per-patient digital twin: turn one patient's real CGM into a dose recommendation.

This is where the evidence base (`analysis.py`) and the mechanism (`model.py`) meet:
for an individual patient we read their circadian phase off their *own* glucose
rhythm, then ask the chronopharmacology model for the dose time that best fits it.
Run across the real cohort, it answers the question that decides whether RhythmRX is
a product or a slogan: **how often does the personalized recommendation actually
differ from the clinic's one-size time?**

### The phase proxy, stated honestly

The ShanghaiT2DM data gives glucose, not cortisol, so here the patient's circadian
phase is read from the **acrophase of their own diurnal glucose rhythm** — the
observable circadian signal that is actually in the data. In a deployed product this
proxy is replaced (or refined) by the cortisol spit-strip and wearable temperature.
The point this module makes does not depend on the exact biomarker: real patients'
rhythms differ, so their best dose times differ.
"""
from __future__ import annotations

import statistics
from datetime import datetime

from rhythmrx.analysis import acrophase, hourly_profile
from rhythmrx.model import optimal_dose_time

# A standard day of meals (hour, carb grams) used when a patient's own meal log
# isn't supplied — the comparison is about *timing*, held against a common load.
STANDARD_MEALS = [(8.0, 55.0), (13.0, 70.0), (19.0, 60.0)]

CLINIC_DEFAULT_HOUR = 8.0     # "take it with breakfast"


def infer_phase_from_cgm(readings: list[tuple[datetime, float]]) -> float:
    """The patient's circadian phase proxy = acrophase of their diurnal glucose rhythm."""
    return acrophase(hourly_profile(readings))


def recommend_dose(readings: list[tuple[datetime, float]],
                   meals: list[tuple[float, float]] | None = None) -> dict:
    """Personalized once-daily dose recommendation for one patient's CGM."""
    phase = infer_phase_from_cgm(readings)
    meals = meals or STANDARD_MEALS
    dose = optimal_dose_time(phase, meals)
    return {
        "phase_h": round(phase, 2),
        "recommended_dose_h": dose,
        "hours_from_clinic_default": round(abs(dose - CLINIC_DEFAULT_HOUR), 2),
    }


def personalization_spread(patients: list[tuple[str, list[tuple[datetime, float]]]],
                           meals: list[tuple[float, float]] | None = None,
                           materiality_h: float = 2.0) -> dict:
    """Run the recommendation across real patients and quantify how much it varies.

    `materiality_h` is the gap from the clinic default beyond which a personalized
    recommendation is clinically meaningful rather than rounding noise.
    """
    recs = []
    for _pid, readings in patients:
        prof = hourly_profile(readings)
        if len(prof) < 12:
            continue
        recs.append(recommend_dose(readings, meals))
    doses = [r["recommended_dose_h"] for r in recs]
    moved = [r for r in recs if r["hours_from_clinic_default"] >= materiality_h]
    return {
        "patients": len(recs),
        "recommended_dose_mean_h": round(statistics.mean(doses), 2) if doses else 0.0,
        "recommended_dose_std_h": round(statistics.pstdev(doses), 2) if len(doses) > 1 else 0.0,
        "recommended_dose_range_h": (round(min(doses), 1), round(max(doses), 1)) if doses else (0, 0),
        "pct_materially_different_from_clinic": round(100.0 * len(moved) / len(recs), 1) if recs else 0.0,
        "materiality_threshold_h": materiality_h,
    }
