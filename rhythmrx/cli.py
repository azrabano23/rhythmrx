"""RhythmRX command line.

    rhythmrx analyze   [--limit N]   # real-data circadian glucose evidence (ShanghaiT2DM)
    rhythmrx personalize [--limit N] # per-patient dose recommendations across real patients
    rhythmrx demo                    # the mechanism on a single phase-delayed patient
"""
from __future__ import annotations

import argparse
import json


def _cmd_analyze(args) -> int:
    from rhythmrx.analysis import cohort_summary, hourly_profile
    from rhythmrx.data import load_all_cgm
    patients = load_all_cgm(limit=args.limit)
    profile = hourly_profile([r for _, rs in patients for r in rs])
    print("# mean glucose by hour of day (real ShanghaiT2DM patients)")
    for h in range(24):
        if h in profile:
            print(f"{h:02d}:00  {profile[h]:6.1f}  " + "#" * max(0, int((profile[h] - 100) / 3)))
    print(json.dumps(cohort_summary(patients), indent=2))
    return 0


def _cmd_personalize(args) -> int:
    from rhythmrx.data import load_all_cgm
    from rhythmrx.twin import personalization_spread
    patients = load_all_cgm(limit=args.limit)
    print(json.dumps(personalization_spread(patients), indent=2))
    return 0


def _cmd_demo(args) -> int:
    from rhythmrx.phase import Sample, estimate_phase
    from rhythmrx.model import optimal_dose_time, simulate_day
    # phase-delayed patient: cortisol peaks ~11:00
    samples = [Sample(8, 0.62), Sample(11, 1.0), Sample(14, 0.78), Sample(20, 0.20)]
    phase = estimate_phase(samples)
    meals = [(8.0, 55.0), (13.0, 70.0), (19.0, 60.0)]
    clinic = simulate_day(meals, 8.0, phase)
    dose = optimal_dose_time(phase, meals)
    personalized = simulate_day(meals, dose, phase)
    out = {
        "estimated_phase_h": phase,
        "clinic_default": {"dose_h": 8.0, **clinic},
        "rhythmrx": {"dose_h": dose, **personalized},
        "hyperglycemia_reduction_pct": round(
            100 * (clinic["hyperglycemia_auc"] - personalized["hyperglycemia_auc"])
            / clinic["hyperglycemia_auc"], 1) if clinic["hyperglycemia_auc"] else 0.0,
    }
    print(json.dumps(out, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="rhythmrx")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze"); a.add_argument("--limit", type=int, default=None); a.set_defaults(func=_cmd_analyze)
    pe = sub.add_parser("personalize"); pe.add_argument("--limit", type=int, default=None); pe.set_defaults(func=_cmd_personalize)
    d = sub.add_parser("demo"); d.set_defaults(func=_cmd_demo)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
