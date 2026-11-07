# LocWaste — Professor feedback adjustments

Date: 2026-11-07 · Status: approved by Santiago · Extends `2026-10-31-locwaste-design.md`

## Intent

The professor asked that the project context come before the tools: a public presentation of the
problem, the proposed solution and the CRISP-DM process, with login as the only way into the app.
The approved sketch has three screens: (1) public presentation with four phase buttons and the
sections Definition, Objectives and Results, plus Login; (2) login without the app menu; (3) the
app home with all the tools, after signing in.

## Decisions

1. **Public presentation at `/`.** No app tools. Sections: problem context, proposed solution,
   definition, objectives and results, and four CRISP-DM phases shown as tabs, each with its
   step-by-step:
   - Phase 1 — Business and data understanding: the problem, the sources (UAESP critical points,
     SDP population, Bogotá boundaries), the target question.
   - Phase 2 — Data preparation: zones, synthetic history and its assumptions, UPZ × month table,
     next-month target without leakage.
   - Phase 3 — Modeling and evaluation: baseline, logistic regression and random forest, temporal
     cross-validation, why one model is chosen.
   - Phase 4 — Deployment: the app, citizen reports, risk map, automatic retraining.
   Results show real values read from the active model run (chosen model, macro-F1 vs baseline,
   high-risk UPZ next month) and a message when no run exists.
   About, How it works and CRISP-DM content moves here; their old routes redirect to the matching
   section of `/`. Header: brand and a "Sign in" button only.
2. **Login and register without the app menu:** brand, a "Back to project" link and the form.
3. **The app is behind login.** The tools home moves to `/app` (after login users land there).
   Map, model, reports, admin and the results API require a session. App menu: Home · Risk map ·
   Model · My reports · All reports (admins only) · Admin (admins only).
4. **Admin has two report views:** My reports (own) and All reports (every user's reports, with
   status filter and status change). The Admin page keeps users/roles and retraining.
5. **Map periods:** chips This month (default) · Last month · 3 months · 12 months. "This month"
   is the current UTC calendar month with whatever has been reported so far. The heat map shows
   only the reports of the selected period; UPZ with no reports in that period show no data (no
   fill, no figures, "No reports in this period" in the detail card). Risk predictions keep their
   own layer.
6. Everything in English; same design system; Part 1/2/3 conventions and tests stay green.

## Delivery

Branch `P4-feedback` from `master`. Claude edits the files; Santiago commits in ordered steps
(1–3 commits per block) and merges. No Supabase changes are needed.
