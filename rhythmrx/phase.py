"""Circadian phase estimation from sparse, daytime-only biomarker samples.

The practical, low-cost circadian phase marker for a consumer product is salivary
**cortisol**: it rises to a peak shortly after waking and declines across the day.
From a few timed samples — the RhythmRX "spit strip" (morning / afternoon /
evening) — we fit a 24 h rhythm and read off the patient's phase (the hour the
marker peaks). The same estimator works on any circadian signal sampled a few
times a day: cortisol, wearable skin temperature, or the diurnal mean of a CGM.

The non-obvious requirement: real samples are **daytime-only and few**, so the
naive "project onto sin/cos" trick (which assumes uniform full-day sampling) is
biased. We do a proper least-squares fit of `value ~ m + a·cos(wt) + b·sin(wt)`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

_PERIOD = 24.0
_W = 2.0 * math.pi / _PERIOD


@dataclass(frozen=True)
class Sample:
    """One timed biomarker reading. `hour` is clock time (0–24); `value` any unit."""
    hour: float
    value: float


def _solve3(A: list[list[float]], y: list[float]) -> list[float]:
    """Solve a 3×3 linear system by Gaussian elimination with partial pivoting."""
    M = [row[:] + [y[i]] for i, row in enumerate(A)]
    for col in range(3):
        piv = max(range(col, 3), key=lambda r: abs(M[r][col]))
        M[col], M[piv] = M[piv], M[col]
        if abs(M[col][col]) < 1e-12:
            raise ValueError("degenerate fit — samples not spread across the day")
        for r in range(3):
            if r != col:
                f = M[r][col] / M[col][col]
                M[r] = [M[r][k] - f * M[col][k] for k in range(4)]
    return [M[i][3] / M[i][i] for i in range(3)]


def fit_rhythm(samples: list[Sample]) -> tuple[float, float, float]:
    """Least-squares fit; return (mesor, amplitude, acrophase_hour)."""
    if len(samples) < 3:
        raise ValueError("need at least 3 timed samples to fit a 24 h rhythm")
    A = [[0.0] * 3 for _ in range(3)]
    yv = [0.0, 0.0, 0.0]
    for s in samples:
        basis = [1.0, math.cos(_W * s.hour), math.sin(_W * s.hour)]
        for i in range(3):
            yv[i] += basis[i] * s.value
            for j in range(3):
                A[i][j] += basis[i] * basis[j]
    m, a, b = _solve3(A, yv)
    amplitude = math.hypot(a, b)
    acrophase = (math.atan2(b, a) / _W) % _PERIOD
    return m, amplitude, acrophase


def estimate_phase(samples: list[Sample]) -> float:
    """Patient circadian phase = acrophase (hour the marker peaks), in [0, 24)."""
    return round(fit_rhythm(samples)[2], 3)
