# LocWaste user guide

LocWaste is published at https://limpia-waste.onrender.com. The homepage presents the project and
is public; every other page needs an account. The free Render plan sleeps when idle, so the first
page can take up to a minute to load.

## Roles

| Role | Can do |
|---|---|
| Citizen | Report waste, see the map, check a zone's risk, follow their reports and risk checks, send feedback |
| Administrator | Everything a citizen does, plus moderate reports, manage users, retrain the model, manage collection priorities, see monitoring and answer feedback |

Everyone who registers starts as a citizen. An administrator promotes users in
**Admin → Admin panel → Users**.

## Account

1. **Register** (`/auth/register`): enter your name, email and a password of at least eight
   characters.
2. **Sign in** (`/auth/login`) with your email and password. You land on the app home, with the
   city summary and the reports of this month.
3. **Sign out** with the button at the right of the menu.

## Citizen pages

### Report waste (`/reports/new`)
1. Press **Report waste** in the menu.
2. Click the map where waste is piling up, or search a neighborhood. The locality, UPZ and
   neighborhood are filled in from the pin; points outside urban Bogotá are not accepted.
3. Choose the type of waste and the size, and mark rodents, insects, strong odor or a river
   nearby if they apply. Add a description if it helps.
4. Press **Send report**. The report starts as **open** until an administrator reviews it.

### Map (`/map`)
- **Period:** this month, last month, last 3 months or last 12 months. Zones without reports in
  the period show no data.
- **Layers:** the heat map of reports, and the risk layer that colors each UPZ by the active
  model's next-month risk (green low, orange medium, red high).
- **Search** a neighborhood or UPZ, and click a zone to open its card: locality, reports in the
  period, critical points, predicted level and probability, and **Check risk now**.

### Risk check (`/risk-check`)
Pick a UPZ, or come from the zone card or from My reports. The active model returns next month's
level and the probability of each class, with an explanation of how to use the result and its
limits: it is a forecast from reports, not a measurement of waste on the ground.

### My reports (`/reports/mine`)
Your reports with their zone and status: **open**, **in progress**, **closed** or **rejected**.
"Check this zone's risk" opens the risk check for that UPZ.

### Inference history (`/inferences`)
Your risk checks with the model version, zone, result, duration and status.

### Model (`/model`)
The active model version: parameters, cross-validation mean ± std of every model, test metrics
against the baseline, confusion matrix and feature importances.

### Help and feedback (`/help`)
Open it from the question mark in the menu; the page you came from is attached. Choose
**incident**, **bug** or **suggestion**, describe it and send it. Follow its status and the
administrator's answer under **My tickets**.

## Administrator pages

### All reports (`/admin/reports`)
Moderate every report. Move valid ones to **in progress** or **closed**; mark false ones
**rejected**, so they never reach the model.

### Admin panel (`/admin`)
- **Users:** change a user's role between citizen and administrator.
- **Retrain:** train a new model version now. Training also starts by itself after 50 new citizen
  reports.

### Collection priorities (`/admin/priorities`)
Every training run creates a pending task for each high-risk UPZ of the predicted month. For each
task: **schedule** a collection date, mark it **done** (optionally closing that zone's open
reports) or **dismiss** it with a note. The pending count appears on the app home and the Admin
page.

### Monitoring (`/admin/monitoring`)
- Last 7 days: requests, average response time, risk checks and their latency, errors and the age
  of the active model.
- Outcomes: accuracy, macro-F1 and confusion matrix of every predicted month that is complete.
- Drift check (PSI of the report rate above 0.2, or a waste type, size or vector share moving
  more than 10 points) and performance check (live macro-F1 below 80% of the cross-validation
  score). Any flag shows a retraining recommendation with **Retrain now**.

### Feedback (`/admin/feedback`)
Every ticket with its user, kind, page and message. Set it to **in review** while working on it
and to **resolved** with an answer; the user sees the answer under My tickets.
