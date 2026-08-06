# Draft slot 3 plan

The user drafts third in a four-manager snake draft. Overall selections are:

`3, 6, 11, 14, 19, 22, 27, 30, 35, 38, 43, 46, 51, 54, 59`

The first turnaround is short: two selections occur between picks 3 and 6.
Later gaps alternate between four and two opponent selections. Preseason waiver
priority is second because the initial waiver order reverses the draft order.

## Pick 3 opening tree

Using the official-data snapshot refreshed on 2026-08-06:

1. Select Erling Haaland if available.
2. Otherwise select Bruno Fernandes if available.
3. If both have gone, current order is Igor Thiago, Gabriel Magalhães, then João Pedro.

This order must be regenerated after the final official-data refresh and after
the first two actual selections. Do not follow the static list when live injury
news or player availability has changed.

## Deterministic rehearsal

If all four managers always take the model's highest legal recommendation, the
slot-3 path begins Igor Thiago at pick 3, Ollie Watkins at pick 6, Morgan
Gibbs-White at pick 11, and Declan Rice at pick 14. This is a rehearsal baseline,
not a forecast that the other managers will act rationally. The live assistant
must record every selection and recalculate immediately.

## Live procedure

1. Record picks 1 and 2 exactly as displayed by the FPL Draft room.
2. Request the top recommendation plus at least two fallbacks.
3. Record the user's selection as `mine`.
4. Record both selections made by manager 4 at the turn.
5. Recalculate for pick 6 rather than relying on the rehearsal list.
6. Continue until all 15 positional roster slots are filled.
