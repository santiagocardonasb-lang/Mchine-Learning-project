# LocWaste — Operations, monitoring and feedback (R3A3 Speaking Models)

Date: 2026-11-15 · Status: approved by Santiago · Extends `2026-10-31-locwaste-design.md` and
`2026-11-07-professor-feedback-design.md`

## Intent

Activity R3A3 asks for a complete web information system that uses the selected model inside the
business process, with an inference history, monitoring, comparison against actual outcomes,
drift checks, and incident/feedback procedures. LocWaste already covers registration, roles,
reports, the risk map and training; this extension closes the remaining gaps.

## Decisions

1. **On-demand zone inference.** Any signed-in user can ask for the risk of one UPZ (from the map
   detail card, from one of their reports, or from a zone selector on a "Risk check" page). The
   server loads the active model artifact, builds that UPZ's features from the stored reports with
   the same preprocessing and feature list used in training (`ml/features.py`, `ml/config.py`),
   and predicts level and class probabilities. The page explains the result, its practical use
   and its limitations.
2. **Inference history.** New table `inference_logs`: created_at, user_id (null for automatic
   runs), model_run_id (model version), upz_id (null for batch runs), kind (`zone`, `batch`),
   predicted level, probability, duration_ms, status (`ok`, `error`) and an error message. Every
   on-demand inference and every training run's batch prediction writes a row. Users see their
   own history; admins see all.
3. **From prediction to action: collection priorities.** New table `collection_tasks`: upz_id,
   model_run_id, period, risk level/probability, status (`pending` → `scheduled` → `done`, or
   `dismissed`), scheduled_for (date), notes, created_at, updated_by. When a training run
   produces predictions, a pending task is created for every high-risk UPZ that has no open task
   for that period. Admins manage them on a "Collection priorities" page (filter, schedule, mark
   done or dismiss with a note). Reports in a UPZ with a done task can be closed from the same
   page. This is the workflow that connects the model to a decision.
4. **Monitoring.** New table `app_events`: created_at, kind (`request`, `inference`, `error`),
   path, method, status_code, duration_ms, user_id, message. A request hook records the response
   time of app requests (static files excluded); an error handler records unhandled exceptions;
   inference services record their own events. Admin "Monitoring" page with indicators: requests
   and average response time (last 7 days), inference count and average latency, errors with the
   latest messages, active model version and age.
5. **Predictions vs actual outcomes.** For every past prediction period that is now a complete
   month, compute the actual level of each UPZ from the stored reports with that run's own cut
   points, then show accuracy, macro-F1 and a confusion matrix per period on the Monitoring page.
6. **Drift and performance checks.** Compare the last complete month with the training data:
   population stability index of the report rate, and shifts in the share of waste types, sizes
   and vectors. Flag drift above a configurable threshold (`ml/config.py`). Flag a performance
   drop when live macro-F1 falls below a configurable fraction of the stored cross-validation
   macro-F1. Both flags recommend retraining on the Monitoring page.
7. **Incidents and feedback.** New table `feedback`: user_id, kind (`incident`, `bug`,
   `suggestion`), message, page, status (`open` → `in_review` → `resolved`), admin response,
   timestamps. Every signed-in user has a "Help & feedback" form and sees their own tickets;
   admins manage all of them. The procedure is documented in the user manual.
8. Model versioning is the ModelRun id plus its params and trained_at; old artifacts stay pruned
   but their metrics, predictions and inference logs remain.
9. Everything in English, same design system, server-side authorization on every route, tests
   for each piece, one migration for the new tables.

## Delivery

Branch `P5-operations` from `master`. Claude edits the files; Santiago commits in ordered steps
and merges; Santiago runs `flask db upgrade` against Supabase after the merge. Then the technical
report (PDF, APA 7, English) is produced with screenshots of the deployed system.
