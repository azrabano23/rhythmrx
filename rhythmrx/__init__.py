"""RhythmRX — chronotherapy for diabetes: measure the patient's clock, time the dose.

Public surface:
  - phase.py    : circadian phase from sparse cortisol / wearable / CGM samples
  - model.py    : insulin-sensitivity rhythm, glucose simulation, optimal dose time
  - analysis.py : circadian-glucose evidence over real CGM cohorts
  - data.py     : ShanghaiT2DM real-CGM loader (download-on-demand)
  - twin.py     : per-patient digital twin -> personalized dose recommendation
"""
from rhythmrx.phase import Sample, estimate_phase, fit_rhythm
from rhythmrx.model import (
    insulin_sensitivity,
    optimal_dose_time,
    simulate_day,
)
from rhythmrx.twin import recommend_dose, personalization_spread

__version__ = "0.1.0"

__all__ = [
    "Sample",
    "estimate_phase",
    "fit_rhythm",
    "insulin_sensitivity",
    "optimal_dose_time",
    "simulate_day",
    "recommend_dose",
    "personalization_spread",
]
