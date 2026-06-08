"""RhythmRX demo API + web page (FastAPI).

    pip install -e ".[app,data]"
    uvicorn app.main:app --reload      # then open http://localhost:8000

Endpoints:
  POST /api/recommend   cortisol samples (+ optional meals) -> phase, dose, glucose curves
  GET  /api/cohort      real ShanghaiT2DM circadian-glucose summary (cached, lazy)
  GET  /api/validation  model-vs-real validation (cached, lazy)
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

from rhythmrx.phase import Sample, estimate_phase
from rhythmrx.model import HYPER, TARGET, insulin_sensitivity, meal_excursion, \
    med_clearance, optimal_dose_time, simulate_day

app = FastAPI(title="RhythmRX")
_STATIC = Path(__file__).resolve().parent / "static"
_DEFAULT_MEALS = [(8.0, 55.0), (13.0, 70.0), (19.0, 60.0)]
CLINIC_HOUR = 8.0


class CortisolPoint(BaseModel):
    hour: float
    value: float


class RecommendRequest(BaseModel):
    cortisol: list[CortisolPoint]
    meals: list[tuple[float, float]] | None = None


def _glucose_curve(meals, dose_hour, phase, potency=70.0):
    out = []
    t = 6.0
    while t <= 24.0:
        g = TARGET + sum(meal_excursion(t, mh, c) for mh, c in meals)
        g = max(TARGET * 0.7, g - med_clearance(t, dose_hour, phase, potency))
        out.append([round(t, 2), round(g, 1)])
        t += 0.5
    return out


@app.get("/")
def index():
    return FileResponse(_STATIC / "index.html")


@app.post("/api/recommend")
def recommend(req: RecommendRequest):
    phase = estimate_phase([Sample(p.hour, p.value) for p in req.cortisol])
    meals = req.meals or _DEFAULT_MEALS
    dose = optimal_dose_time(phase, meals)
    clinic = simulate_day(meals, CLINIC_HOUR, phase)
    personalized = simulate_day(meals, dose, phase)
    a0, a1 = clinic["hyperglycemia_auc"], personalized["hyperglycemia_auc"]
    return {
        "phase_hour": phase,
        "recommended_dose_hour": dose,
        "clinic_dose_hour": CLINIC_HOUR,
        "clinic": clinic,
        "personalized": personalized,
        "hyperglycemia_reduction_pct": round(100 * (a0 - a1) / a0, 1) if a0 else 0.0,
        "sensitivity_curve": [[h, round(insulin_sensitivity(h, phase), 3)] for h in range(6, 24)],
        "glucose_clinic": _glucose_curve(meals, CLINIC_HOUR, phase),
        "glucose_personalized": _glucose_curve(meals, dose, phase),
        "hyper_threshold": HYPER,
    }


@lru_cache(maxsize=1)
def _cohort():
    from rhythmrx.analysis import cohort_summary
    from rhythmrx.data import load_all_cgm
    return cohort_summary(load_all_cgm())


@lru_cache(maxsize=1)
def _validation():
    from rhythmrx.data import load_all_sessions
    from rhythmrx.validation import validate
    return validate(load_all_sessions())


@app.get("/api/cohort")
def cohort():
    return _cohort()


@app.get("/api/validation")
def validation():
    return _validation()
