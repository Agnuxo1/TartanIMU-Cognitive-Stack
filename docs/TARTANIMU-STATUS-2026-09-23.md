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

This public software release contains no Kaggle submission receipt, accepted
entry ID, competition prediction CSV, or official score-service result. It
makes no claim about any participant's submission status, rank, or eligibility.

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

### Public code-sharing rule

Section 6 of the live [Kaggle Rules](https://www.kaggle.com/competitions/tartan-imu-challenge-iros2026/rules)
defines “Competition Code” broadly and says that code shared publicly under that
rule must also be shared on the competition's Kaggle discussion forum or
notebook. This GitHub release contains only synthetic TartanIMU contract helpers
and tests, not official competition data, prediction code, or a trained model.
Whether these synthetic helpers count as “other code relevant to the
Competition” is unresolved. No Kaggle forum post or notebook has been made; do
not claim complete rules compliance unless applicability is confirmed.

## Decision and remaining evidence request

Eligibility cannot be established from this software repository alone. Before
filing any organizer form or report, the team must verify an accepted prediction
submitted by the deadline and match it to the exact CSV, official scoring
output, reproducible model artifacts, public Hugging Face revision, and form or
report receipts. If this evidence is unavailable, do not claim eligibility or
invent results. The public software repository is a separate deliverable and
makes no contest-performance claim.

## Official task contract

The challenge asks for one platform-blind model that maps raw 200 Hz, six-axis
IMU windows to body-frame velocity `(vx, vy, vz)` in m/s. Its published score
combines normalized AVE and ATE20 with weights 0.6 and 0.4 respectively; lower
is better and the four platforms are macro-averaged. The formula in this
repository accepts supplied AVE/ATE20 values; it does not reproduce trajectory
alignment, the scoring service, or official leaderboard results.
