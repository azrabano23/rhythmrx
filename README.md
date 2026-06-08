# RhythmRX — chronotherapy for diabetes

[![tests](https://github.com/azrabano23/rhythmrx/actions/workflows/tests.yml/badge.svg)](https://github.com/azrabano23/rhythmrx/actions/workflows/tests.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Same pill, same dose, different hour — measurably better control.** RhythmRX
measures a patient's circadian phase from a cheap biomarker and times their diabetes
medication to it. The engine here estimates phase, models the patient's insulin-
sensitivity rhythm, and recommends the dose time that minimizes their glycemic
burden — and it's validated against **real continuous-glucose data from 100 type-2
patients**, where it turns out **94.5% of people should not be dosing when the clinic
tells them to.**

---

## The problem

Insulin sensitivity and glucose tolerance are under circadian control — the body's
ability to clear glucose, and to use a drug that helps, rises and falls across the
biological day ([Stenvers et al., *Nat Rev Endocrinol* 2019](https://www.nature.com/articles/s41574-018-0122-1)).
"Chronotherapy" means dosing in step with that rhythm, and the timing genuinely
moves outcomes: in a randomized trial, metformin taken *before* breakfast lowered
glucose AUC significantly more than the same dose after ([Gillen et al., 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC11607888/)).

The catch: **nobody measures *your* rhythm.** The clinic says "take it with
breakfast" — a fixed clock time that assumes every patient's clock is identical. The
people that's most wrong for are shift workers, late chronotypes, and the sleep-
disrupted, whose clocks are *shifted*. Globally that's an enormous population — the
IDF counts **~537 million adults with diabetes**.

## The real-data evidence

The argument isn't hypothetical. Run RhythmRX's analysis over the
[**ShanghaiT2DM**](https://doi.org/10.1038/s41597-023-01940-7) dataset (Zhao et al.,
*Sci Data* 2023 — 15-min CGM for 100 real type-2 patients, **109 sessions /
112,462 readings**):

| Finding (real patients) | Value |
|---|---|
| Mean glucose | 140 mg/dL |
| Time in range (70–180) | 79% |
| **Dawn phenomenon** (overnight trough → 08:00) | **+55 mg/dL** |
| **Spread of each patient's personal glucose-peak time** | **σ = 3.1 h, 02:00–23:30** |
| **Patients whose personalized dose time differs materially (≥2 h) from "with breakfast"** | **94.5%** |

Two things fall straight out of real data. First, glucose **is** strongly circadian —
the dawn phenomenon (glucose climbing ~55 mg/dL into the morning before a bite of
breakfast) is right there. Second, and decisively: **each patient's rhythm is
different.** Their peak times spread across the entire clock, and when you run the
per-patient recommender (`rhythmrx personalize`), **94.5% of real patients get a dose
time that is materially different from the clinic default.** A fixed hour is, for
almost everyone, the wrong hour.

## How it works

```
cortisol strip / wearable / CGM  ──▶  phase.py     ──▶  patient circadian phase
                                                          │
patient phase ──▶ model.py (insulin-sensitivity rhythm + glucose sim) ──▶ optimal dose time
                                                          │
real CGM ──▶ twin.py: infer this patient's phase ──▶ personalized recommendation
                                                          │
       analysis.py ──▶ circadian-glucose evidence across a whole cohort
```

1. **`phase.py`** — recover circadian phase from a few *daytime-only* biomarker
   samples (the spit strip) via a proper least-squares 24 h fit — not the biased
   projection that assumes full-day sampling.
2. **`model.py`** — a phase-anchored insulin-sensitivity rhythm (high in the
   biological day, low in the evening — the shape behind evening glucose intolerance),
   a glucose-excursion simulator, and a dose-time optimizer. A dose taken when the
   body is most insulin-sensitive does more work; that's the mechanism, in one line.
3. **`twin.py`** — the per-patient digital twin: read a patient's phase off their own
   CGM rhythm and return their personalized dose time. Run across a cohort, it
   quantifies how often personalization actually changes the answer.
4. **`analysis.py` / `data.py`** — the real-data layer over ShanghaiT2DM
   (download-on-demand, gitignored).

## Results

- **Mechanism** (`rhythmrx demo`, a phase-delayed patient): personalizing the dose
  time cuts modelled hyperglycemia burden **~39%** and lifts time-in-range
  **66% → 77%** vs. the fixed 08:00 dose.
- **Real cohort, real meals** (`rhythmrx personalize`): run over all 109 patients
  using **each patient's own logged meals**, recommended dose times span 06:00–15:30
  and **94.5% differ materially (≥2 h) from the clinic's "with breakfast".**

## Validation against real data

The model makes a falsifiable claim — insulin sensitivity is circadian, high in the
biological day, low at night — and the ShanghaiT2DM data can test it, because it has
CGM *and* timestamped, weighed meals. `rhythmrx.validation` measures the **glycemic
response per gram of food** for every real meal (excursion ÷ meal size, to control
for big-vs-small meals) and bins it by hour:

| Real meal hour | Glycemic response per gram (mg/dL / g) |
|---|---|
| 10:00–11:00 (most insulin-sensitive) | **0.14–0.18** (lowest) |
| 13:00–15:00 (post-lunch dip) | ~0.55 |
| 22:00–00:00 (evening intolerance) | **1.9–3.6** (highest) |

This is textbook **evening glucose intolerance, straight out of real patients** — the
same body, the same food, produces a far larger glucose spike at night than mid-
morning. The model's sensitivity curve correlates with this real response at
**r ≈ 0.54** (Pearson over 20 hourly bins), and its peak is **calibrated to the
empirical sensitivity peak of 10:00** read directly off the data (`SENS_PEAK_OFFSET`).
So the dosing recommendations rest on a sensitivity rhythm that is *measured*, not
assumed.

## Technical breakdown

Stdlib-only core (the `phase`/`model`/`twin`/`analysis`/`validation` math has no heavy
deps, so every number is attributable and the tests run anywhere); pandas + xlrd only
for reading the real Excel CGM files, FastAPI only for the demo. A least-squares
circadian fit that works on sparse daytime samples; a chronopharmacology model linking
phase → sensitivity → dose effect, **calibrated and validated against real post-meal
excursions**; a glucose-excursion simulator; a per-patient digital twin that uses each
patient's real meal log; a real-data pipeline that downloads, parses, and analyzes 112k
CGM readings; and a FastAPI web demo. **11 tests** (offline fixtures + real-data-gated +
API), CLI, CI on 3.10/3.12.

## Honest framing

Circadian glucose regulation and the *direction* of the chronotherapy effect are
well established, and the cohort findings above are **measured on real patients**.
The dose-response *magnitude* in the mechanism demo is **model-internal and
illustrative**, not a clinical result, and some widely-quoted single-trial
percentages in this field (e.g. specific bedtime-dosing cardiovascular figures) are
**contested or under review** and are deliberately not asserted here. RhythmRX's
claim is the robust one, and the real data backs it: *dosing to the individual's
measured rhythm beats a fixed clock time, for almost everyone.* This is decision
support; it does not replace a clinician or a trial.

## The product this engine powers

A **$5 cortisol spit-strip + app**: spit three times across a day, scan with your
phone, and the app estimates your rhythm and tells you when to take your medication —
with an optional adherence band, and the same phase data unlocking sleep / focus /
fertility-window insights. The health-equity case is the point (UN **SDG 3** good
health, **SDG 10** reduced inequality): precision chronotherapy today means a
concierge workup; a $5 strip democratizes it.

## Run it

```bash
pip install -e ".[data,app]"       # data: pandas+xlrd for real CGM · app: FastAPI demo
rhythmrx demo                      # the mechanism on one phase-delayed patient
rhythmrx analyze                   # real circadian-glucose evidence (downloads ~3.7MB once)
rhythmrx personalize               # per-patient dose recommendations across 100 real patients
pytest -q

# clickable web demo: enter your 3 cortisol readings, get your dose time + glucose curves
uvicorn app.main:app --reload      # http://localhost:8000
```

The web app (`app/`) is a self-contained FastAPI service: a `/api/recommend` endpoint
(cortisol samples → phase, dose, before/after glucose curves), plus `/api/cohort` and
`/api/validation` exposing the real-data findings, behind a single-page UI.

## References

- Stenvers, D.J. et al. (2019). *Circadian clocks and insulin resistance.* Nat Rev Endocrinol 15, 75–89.
- Gillen, J.B. et al. (2024). *Morning exercise and pre-breakfast metformin interact to reduce glycaemia in type 2 diabetes: a randomized crossover trial.* Diabetes Obes Metab.
- Zhao, Q. et al. (2023). *Chinese diabetes datasets for data-driven machine learning.* Scientific Data 10, 35. (ShanghaiT1DM / ShanghaiT2DM; CC-BY 4.0.)
- International Diabetes Federation, *IDF Diabetes Atlas* (10th ed.).

## License

MIT — see [LICENSE](LICENSE). Author: **Azra Bano**.
