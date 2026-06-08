"""Validate the insulin-sensitivity model against real post-meal glucose excursions.

The model claims insulin sensitivity is circadian — high in the biological day, low
in the evening. That claim is *testable* on the ShanghaiT2DM data, which has both CGM
and timestamped, weighed meals. For every real meal we measure the **glycemic
response per gram of food** (how far glucose rose, divided by meal size, to control
for big-vs-small meals). If the model is right, that response should be *smallest*
when the body is most insulin-sensitive and *largest* in the evening — i.e. the real
response-per-gram curve should run opposite to the model's sensitivity curve.

This module computes that real curve, reports its correlation with the model, reads
the **empirical** insulin-sensitivity peak straight off the data, and calibrates the
model's peak to match it.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta

from rhythmrx.model import insulin_sensitivity


def meal_responses(cgm: list[tuple[datetime, float]], meals: list[tuple[datetime, float]],
                   window_h: float = 2.0) -> list[tuple[float, float, float]]:
    """For each meal -> (meal_hour, glucose_excursion mg/dL, grams).

    Excursion = peak CGM within `window_h` after the meal minus the CGM at the meal.
    """
    cgm = sorted(cgm)
    out = []
    for mt, grams in meals:
        pre = None
        peak = None
        for ts, g in cgm:
            if ts <= mt and (pre is None or ts >= pre[0]):
                pre = (ts, g)
            if mt <= ts <= mt + timedelta(hours=window_h):
                peak = g if peak is None else max(peak, g)
        if pre is None or peak is None or grams <= 0:
            continue
        out.append((mt.hour + mt.minute / 60.0, peak - pre[1], grams))
    return out


def response_per_gram_by_hour(sessions: list[tuple[str, dict]]) -> dict[int, float]:
    """Mean glycemic response per gram of food, binned by meal hour, across patients."""
    sums: dict[int, float] = {}
    counts: dict[int, int] = {}
    for _pid, s in sessions:
        for hour, exc, grams in meal_responses(s["cgm"], s["meals"]):
            h = int(hour)
            sums[h] = sums.get(h, 0.0) + exc / grams
            counts[h] = counts.get(h, 0) + 1
    return {h: sums[h] / counts[h] for h in sorted(sums) if counts[h] >= 3}


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    vy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return cov / (vx * vy) if vx and vy else 0.0


def validate(sessions: list[tuple[str, dict]], ref_phase: float = 8.0) -> dict:
    """Compare the real response-per-gram curve to the model's sensitivity curve.

    Returns the correlation (model resistance vs. real response — positive means the
    model's shape matches reality), the empirical sensitivity peak read off the data,
    the model's peak, and a calibrated phase offset that best aligns them.
    """
    real = response_per_gram_by_hour(sessions)
    hours = sorted(real)
    if len(hours) < 6:
        raise ValueError("not enough meal coverage to validate")

    real_vals = [real[h] for h in hours]
    # model "resistance" = 1 - sensitivity (should track real response/gram)
    model_resist = [1.0 - insulin_sensitivity(h, ref_phase) for h in hours]
    corr = _pearson(real_vals, model_resist)

    # empirical sensitivity peak = hour of LOWEST response per gram
    emp_peak = min(real, key=real.get)
    from rhythmrx.model import SENS_PEAK_OFFSET
    model_peak = (ref_phase + SENS_PEAK_OFFSET) % 24.0

    # calibrate: find the phase whose sensitivity curve best anti-correlates with response
    best_phase, best_corr = ref_phase, corr
    p = 0.0
    while p < 24.0:
        mr = [1.0 - insulin_sensitivity(h, p) for h in hours]
        c = _pearson(real_vals, mr)
        if c > best_corr:
            best_corr, best_phase = c, p
        p += 0.5

    return {
        "n_hours": len(hours),
        "correlation_model_vs_real": round(corr, 3),
        "empirical_sensitivity_peak_hour": emp_peak,
        "model_sensitivity_peak_hour": round(model_peak, 1),
        "calibrated_phase_hour": round(best_phase, 1),
        "calibrated_correlation": round(best_corr, 3),
    }
