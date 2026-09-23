# TartanIMU challenge status — 2026-09-23

This is an evidence note, not a competition entry or a claim of rank.

![TartanIMU task contract and evidence status](../assets/tartanimu-evidence.svg)

## Workspace evidence

The repository contains deterministic, synthetic-data contract utilities and
unit tests for IMU window shape, grouped folds, leakage checks, macro-AVE
helpers, and the published score formula. It does **not** contain authorized
competition data, a trained challenge model, trained weights, the 30,644-row
prediction CSV, or an official score-service result. These helpers are not a
reimplementation of the full official evaluator.

The user's private Kaggle submission history could not be verified in this
workspace. Missing local artifacts and an HTTP 403 response do not establish
that no timely Kaggle upload exists. No submission ID, score, or rank is claimed.

## Official eligibility and deadlines

The organizer's [detailed setup and timeline](https://superodometry.com/imuchallenge/setup/),
[challenge page](https://superodometry.com/imuchallenge/), and
[Kaggle competition](https://www.kaggle.com/competitions/tartan-imu-challenge-iros2026)
state that:

- Prediction submissions closed **2026-09-20 at 23:55 UTC**.
- The setup timeline and the organizer's August 1 announcement place both the
  final Kaggle submission and model weights at **2026-09-20, 23:55 UTC**. Do not
  assume the later report deadline extends the model-publication deadline.
- The technical report is due **2026-09-23 at 23:59 US Eastern (EDT)**, which is
  **2026-09-24 at 03:59 UTC / 05:59 in Madrid**.
- Final-ranking eligibility requires a timely Kaggle submission, a form entry
  attaching that exact CSV, a technical report, and public unified-model weights
  plus inference code. The organizer page's phrase “within the same 7 days” does
  not specify its anchor; its setup timeline and August 1 update give September
  20 for the final submission and weights.
- Report values in the specified tables must come from the organizer's scoring
  service, not a local implementation.

### Conflicting organizer deadline text

The organizer's [About page](https://superodometry.com/imuchallenge/about/)
groups the technical report with the September 20 deadline. In contrast, the
more detailed setup timeline and the dated September 4 announcement explicitly
give the report a September 23, 23:59 EDT deadline; this note records that later,
specific report deadline, not an extension of the prediction or model-weight
deadlines. The eligibility paragraph's “within the same 7 days” wording for the
public model repository remains ambiguous. Any claim that model weights were
accepted after September 20 needs organizer confirmation and dated evidence.

## Decision and remaining evidence request

A real JEV 1.13.0 query classified eligibility as `not_verified_private_state`
and recommended that the account owner inspect the private Kaggle submissions
now (reported probability 0.82; confidence 0.76). JEV cannot see or prove the
private account history. The remaining decisive evidence is the submission ID,
timestamp, exact submitted CSV, scoring-service output, and runnable model
artifacts. If those cannot be substantiated before the report deadline, do not
file a report that implies contest eligibility or invents results. The public
software repository is a separate deliverable and explicitly makes no contest
performance claim.

## Official task contract

The challenge asks for one platform-blind model that maps raw 200 Hz, six-axis
IMU windows to body-frame velocity `(vx, vy, vz)` in m/s. Its published score
combines normalized AVE and ATE20 with weights 0.6 and 0.4 respectively; lower
is better and the four platforms are macro-averaged. The formula in this
repository accepts supplied AVE/ATE20 values; it does not reproduce trajectory
alignment, the scoring service, or official leaderboard results.
