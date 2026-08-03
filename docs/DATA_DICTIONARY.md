# Modeling table data dictionary

Each row represents the information available for one player immediately before one Gameweek deadline.

| Column | Meaning |
|---|---|
| `season` | Season containing the prediction date |
| `gameweek` | Gameweek being predicted from |
| `cutoff_time` | Timestamp after which no feature data may be used |
| `player_id` | Stable source ID, namespaced by source and season if necessary |
| `player_name` | Display name for review only, not the primary join key |
| `team_id` | Club at the cutoff time |
| `position` | `GK`, `DEF`, `MID`, or `FWD` |
| `age` | Player age at cutoff |
| `minutes_last_3/6/12` | Rolling minutes before cutoff |
| `starts_last_3/6/12` | Rolling starts before cutoff |
| `points_last_3/6/12` | Rolling FPL points before cutoff |
| `goals_per90` | Smoothed historical goals per 90 |
| `assists_per90` | Smoothed historical assists per 90 |
| `bonus_per90` | Smoothed historical bonus per 90 |
| `team_attack_form` | Leakage-safe team attack rating |
| `team_defence_form` | Leakage-safe team defence rating |
| `fixture_strength_next_6` | Weighted difficulty of the next six fixtures |
| `home_matches_next_6` | Home matches in target horizon |
| `rest_days_next_match` | Days between scheduled matches |
| `availability_flag` | Known injury/suspension/selection status at cutoff |
| `points_next_6` | Training target; sum of later FPL points in horizon |
| `minutes_next_6` | Training target; sum of later minutes in horizon |

Raw input files, feature tables, model artifacts, and predictions belong in separate directories. Generated data is ignored by Git except for the synthetic sample.
