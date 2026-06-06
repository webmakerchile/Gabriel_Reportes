---
name: Weekly report dual-emitter dedup
description: Why the Saturday weekly per-vendedor report had two emitters and how the seeded ReporteProgramado rows are constrained (can't be deactivated/deleted).
---

# Saturday weekly report: two emitters, one allowed

The per-vendedor weekly report can be sent by TWO independent paths, which
historically caused a duplicate Saturday email per salesperson:
1. The dedicated cron `weekly_saturday_reports` (the intended single emitter).
2. `process_scheduled_reports` (runs every ~15 min) processing the 5 SEEDED
   `ReporteProgramado` rows (frecuencia=semanal, tipo=individual, dia_semana=5,
   tracked vendedor, 06:30).

**Why the seeded rows can't just be deactivated/deleted:** the daily/weekly crons
and the Monday cobranza job all read `emails_destino` (per-vendedor recipient
list) from these rows, filtering `activo == True`. Deactivating them would break
recipient lookup for ALL automated reports, not just the weekly.

**How to dedup safely:** exclude the seeded rows from sending in
`process_scheduled_reports` (keep the cron as the single emitter) instead of
touching the rows. The robust discriminator is `dia_semana == 5`: the dashboard
schedule-creation UI only offers Mon–Fri (dia_semana 0–4), so Saturday is
exclusive to the seed — no user-created schedule can be suppressed by accident.
Side effect: those rows then never advance
ultima_ejecucion/total_enviados/proxima_ejecucion, so their "next run" shown in
the schedules UI goes stale; acceptable because they function as email-config
holders, not active senders.

**General rule:** before deleting/deactivating a "config" row that also happens to
drive a job, check every reader — these rows are dual-purpose (recipient config +
legacy sender), and the safe fix targets the behavior (sending), not the row.
