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

The organizer's [setup guide](https://superodometry.com/imuchallenge/setup/)
says competition dates may change and directs participants to the live Kaggle
pages as the source of truth. The signed-in, read-only [Kaggle Rules tab](https://www.kaggle.com/competitions/tartan-imu-challenge-iros2026/rules)
currently states:

- Prediction submissions closed **2026-09-20 at 23:55 UTC**.
- The current Kaggle Rules timeline gives **2026-09-27 at 23:55 UTC** for both
  the technical report and model weights (**2026-09-28 at 01:55 in Madrid**).
- To qualify for the final ranking, a team also needs a form for each leaderboard
  submission considered, attaching the exact prediction CSV; a PDF report; and a
  public Hugging Face repository containing the frozen unified-model weights, a
  runnable inference entry point, pinned `requirements.txt`, and that exact
  `submission.csv`. Organizers re-execute the model. The Rules page allows one
  72-hour repair window if the code fails, with a single GPU (at most 16 GB VRAM),
  two hours wall-clock, and no internet access.
- Report values in the specified tables must come from the organizer's scoring
  service, not a local implementation.

### Conflicting official deadline text

The organizer's [About page](https://superodometry.com/imuchallenge/about/)
still groups the report and weights with the September 20 deadline; its
[setup timeline](https://superodometry.com/imuchallenge/setup/) gives the report
as September 23 and weights as September 20. The live Kaggle Rules page now gives
September 27 for both. Because the setup guide says to follow live Kaggle rules
when dates change, this status note uses the current Rules-tab date while
recording the discrepancy; recheck it before filing. The September 20 prediction
deadline is unchanged. No extension can create a new eligible prediction after
that close.

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
