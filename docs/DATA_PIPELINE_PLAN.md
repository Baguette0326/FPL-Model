# Data pipeline and storage plan

## Architecture

```text
Public historical CSVs + official current API
                    |
                    v
       Immutable checksummed raw snapshots
                    |
                    v
      Leakage-safe player/Gameweek table
                    |
          +---------+----------+
          |                    |
          v                    v
   Model experiments      SQLite event store
                               |
                               v
              Draft, waivers, free agents, trades
```

Raw source data remains immutable and reproducible. Generated feature tables are rebuildable. SQLite stores operational league state and observed behaviour; it is not used as a replacement for raw evidence.

## Historical extraction

- Ten seasons: 2016/17 through 2025/26
- Stable player-code joins rather than display names
- UTF-8 and legacy Windows-1252 support
- Position/team reconstruction for early files
- Double-Gameweek aggregation
- Exact source URL, byte count, timestamp, and SHA-256 checksum
- Explicit indicators for fields that do not exist in older schemas

The 2019/20 dataset uses event numbering through 47. Preserve the original event order and treat it chronologically; do not assume every season has exactly 38 numbered events.

## SQLite operational data

The local `league.sqlite3` database will contain:

- Four anonymized managers: You, Friend A, Friend B, Friend C
- Current player identities and positions
- Every draft pick in order
- Versioned predictions and uncertainty ranges
- Add/drop roster events
- Ordered waiver claims and outcomes
- Free-agent activity
- Two-sided trades and included players

No passwords, GitHub tokens, or FPL credentials belong in the database.

## Current-season schedule

### Before the draft

1. Refresh current player and fixture snapshots.
2. Record the final transfer/availability cutoff.
3. Generate versioned projections.
4. Initialize four managers and the random draft order.

### During the draft

1. Record every pick immediately.
2. Update all four legal rosters.
3. Persist recommendation version and fallbacks.
4. Allow undo by appending a correction event rather than silently rewriting history.

### Every Gameweek

1. Snapshot official data after results settle.
2. Store prediction inputs before the next deadline.
3. Record waivers, free agents, and trades.
4. Generate lineup and transaction recommendations.
5. After the Gameweek, attach actual outcomes for evaluation.

## Next data tasks

1. Add historical feature-availability indicators and schema-era labels.
2. Add one-Gameweek appearance, start, minutes, and points targets.
3. Add fixture/opponent features using only prior matches.
4. Load the 2026/27 current player pool into SQLite.
5. Implement append-only draft and roster event commands.
6. Create automated source and leakage audit reports.
