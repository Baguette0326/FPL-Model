# Modeling table data dictionary

Each row represents the information available for one player immediately before one Gameweek deadline.

| Column | Meaning |
|---|---|
| `season` | Season containing the prediction date |
| `gameweek` | Original source Gameweek label; not safe for chronological arithmetic |
| `event_sequence` | Contiguous chronological event index within the season |
| `prediction_cutoff` | Earliest fixture timestamp for the event, used as the historical cutoff proxy |
| `available_at` | Latest timestamp of the event supplying the rolling features |
| `player_code` | Stable FPL source code; names are never used as model joins |
| `name` | Display name for review only |
| `team` | Club at the cutoff time |
| `position` | `GK`, `DEF`, `MID`, or `FWD` |
| `fixtures_next_1` | Completed team fixtures in the event at the cutoff: 0 for a blank, 1 normally, 2 for a double, and 3 for a historical triple |
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
| `schema_era` | Data-driven source schema (`core` or `core_expected_stats`) |
| `has_expected_stats_source` | Whether the source season supplies xG/xA fields |
| `has_starts_source` | Whether the source season supplies observed starts (2022/23 onward) |
| `has_availability_source` | Whether historical cutoff-safe availability data exists (currently false) |
| `has_fixture_strength_source` | Whether a historical fixture-strength family exists (currently false) |
| `season_recency` | Number of seasons before the newest historical season |
| `disrupted_schedule` | Season has non-standard or missing source event periods |
| `player_event_observed` | Whether the raw source contained a player row for this event rather than a generated zero row |
| `points_next_6` | Training target; sum of FPL points from the event at the cutoff through the next five events |
| `minutes_next_6` | Training target; minutes over the same six-event horizon |
| `appearance_next_1` | Whether the player records minutes in the event at the cutoff |
| `start_next_1` | Whether the player starts in the event at the cutoff |
| `minutes_next_1` | Minutes in the event at the cutoff |
| `points_next_1` | FPL points in the event at the cutoff |
| `target_1_observed_event` | Event index at which a one-event label is fully observed |
| `target_6_observed_event` | Event index at which a six-event label is fully observed |

Legacy xG/xA values remain null when the historical source did not record that
feature family. A genuine observed zero is retained as zero. Validation must use
`event_sequence` and admit a training label only when its observed-event index is
strictly earlier than the validation event.

Raw input files, feature tables, model artifacts, and predictions belong in separate directories. Generated data is ignored by Git except for the synthetic sample.

The published `modeling_table.csv` and `modeling_table_ml_v2.csv` remain frozen.
`modeling_table_ml_v3.csv` removes non-player Assistant Manager chip records,
canonicalizes positions from player metadata, removes equivalent raw duplicate
player-fixture rows, and adds fixture-count exposure for blank/double/triple events.
The versioned predecessors are never overwritten.
