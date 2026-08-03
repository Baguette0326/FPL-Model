# Week-by-week squad manager

The project continues after the initial draft. Before every Gameweek it should refresh player forecasts, identify trend changes, and recommend legal moves for the current FPL Draft roster.

## Official Draft actions

FPL Draft does not use the regular game's Wildcard chip. The relevant mechanisms are:

- **Waiver request:** prioritized same-position add/drop request, processed before the deadline.
- **Free-agent transfer:** add an unowned player after waivers and before the Gameweek deadline.
- **Trade:** exchange players with another manager when the league's trade setting permits it.

Here, a **wildcard pick** means a speculative breakout or sleeper target—not the official Wildcard chip.

## Weekly forecast horizons

Produce forecasts for the next 1, 3, and 6 Gameweeks plus rest of season. Each should include a median, downside, upside, and expected minutes, using only information available before the upcoming deadline.

## Trend detection

Keep these explainable signals separate:

- **Role:** starts, minutes share, position, set pieces, penalties
- **Threat:** shots, box touches, expected goals, chances created, expected assists
- **Team:** attack/defence form, tactics, and manager changes
- **Fixtures:** difficulty, home/away mix, blanks, doubles, congestion
- **Availability:** injuries, suspensions, return from injury, rotation risk

Use exponentially weighted windows and shrink small samples toward a prior. One goal or clean sheet should not by itself trigger a breakout alert.

## Waivers and free agents

Compare every unowned player with the weakest owned player at the same position:

```text
expected_gain = candidate_hold_value - owned_player_hold_value
```

Rank legal moves using short-horizon points, six-week points, rest-of-season value, role trend, uncertainty, and the chance another manager claims the player. Return the add, drop, expected gain, confidence, explanation, and fallback claims in priority order.

## Trades

Estimate both rosters before and after a proposal. Report expected gain for each manager, positional need solved, short-term versus long-term effect, risk transferred, and whether the other manager may plausibly accept. Evaluate the complete starting lineup and replacement pool, not only the players named in the trade.

## Weekly run schedule

1. After the Gameweek: ingest results and snapshot source data.
2. Early week: update trends and preliminary forecasts.
3. Before waivers: publish targets, drops, and priority order.
4. After waivers: refresh free agents.
5. Before the deadline: update injuries, expected minutes, starting XI, and bench order.
6. Save recommendations and outcomes for continuous backtesting.

## Evaluation

Replay historical weeks and compare against holding, choosing last week's top scorers, and raw projected points. Measure realized add/drop gain over 3 and 6 Gameweeks, regret, breakout precision, and forecast calibration.
