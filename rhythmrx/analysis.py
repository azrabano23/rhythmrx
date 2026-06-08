"""What real CGM data says about circadian glucose — RhythmRX's evidence base.

Over the ShanghaiT2DM cohort these functions recover the circadian glucose profile
(the dawn phenomenon), the cohort's glycemic stats, and — the decisive number — the
spread of each patient's personal glucose-peak time, which determines whether a
fixed dosing hour can ever be right for everyone.
"""
from __future__ import annotations

import math
import statistics
from datetime import datetime

_W = 2.0 * math.pi / 24.0


def hourly_profile(readings: list[tuple[datetime, float]]) -> dict[int, float]:
    """Mean glucose (mg/dL) by hour of day."""
    sums: dict[int, float] = {}
    counts: dict[int, int] = {}
    for ts, g in readings:
        sums[ts.hour] = sums.get(ts.hour, 0.0) + g
        counts[ts.hour] = counts.get(ts.hour, 0) + 1
    return {h: sums[h] / counts[h] for h in sorted(sums)}


def acrophase(profile: dict[int, float]) -> float:
    """Hour of the glucose peak via a 24 h single-harmonic fit of an hourly profile."""
    items = sorted(profile.items())
    if len(items) < 12:
        raise ValueError("need most of the day represented")
    m = sum(v for _, v in items) / len(items)
    a = sum((v - m) * math.cos(_W * h) for h, v in items) * 2.0 / len(items)
    b = sum((v - m) * math.sin(_W * h) for h, v in items) * 2.0 / len(items)
    return (math.atan2(b, a) / _W) % 24.0


def time_in_range(readings: list[tuple[datetime, float]], lo: float = 70.0,
                  hi: float = 180.0) -> float:
    vals = [g for _, g in readings]
    return 100.0 * sum(1 for g in vals if lo <= g <= hi) / len(vals) if vals else 0.0


def dawn_rise(profile: dict[int, float]) -> float:
    """Dawn-phenomenon rise: glucose at 08:00 minus the overnight (0–5 h) trough."""
    trough = min(profile[h] for h in range(0, 6) if h in profile)
    return profile.get(8, trough) - trough


def cohort_summary(patients: list[tuple[str, list[tuple[datetime, float]]]]) -> dict:
    """Aggregate the real-data findings across (patient_id, readings) pairs."""
    all_readings: list[tuple[datetime, float]] = []
    peaks: list[float] = []
    for _pid, readings in patients:
        if not readings:
            continue
        all_readings.extend(readings)
        prof = hourly_profile(readings)
        if len(prof) >= 12:
            peaks.append(acrophase(prof))
    profile = hourly_profile(all_readings)
    vals = [g for _, g in all_readings]
    return {
        "patients": len(peaks),
        "cgm_readings": len(all_readings),
        "mean_glucose": round(sum(vals) / len(vals), 1),
        "time_in_range_pct": round(time_in_range(all_readings), 1),
        "daily_swing_mgdl": round(max(profile.values()) - min(profile.values()), 1),
        "dawn_rise_mgdl": round(dawn_rise(profile), 1),
        "population_peak_hour": round(acrophase(profile), 1),
        "personal_peak_spread_h": round(statistics.pstdev(peaks), 1) if len(peaks) > 1 else 0.0,
        "personal_peak_range_h": (round(min(peaks), 1), round(max(peaks), 1)) if peaks else (0, 0),
    }
