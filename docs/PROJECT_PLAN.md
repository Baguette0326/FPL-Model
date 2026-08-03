# Project plan: 2026/27 four-manager FPL Draft assistant

## 1. Define the decision

The assistant should answer one question repeatedly during a snake draft:

> Given every player already selected, my current roster, my draft position, and the picks before my next turn, which available player gives me the strongest expected season outcome?

The league configuration should be recorded before modeling:

- Four managers
- Official FPL Draft squad: 2 GK, 5 DEF, 5 MID, 3 FWD
- Snake draft order
- Classic or head-to-head league scoring
- Trade setting
- Your draft slot, once known

Classic scoring rewards total expected points. Head-to-head scoring can justify slightly more weight on weekly upside and fixture timing.

## 2. Build the historical dataset

Create one row per player per Gameweek, across at least three complete seasons. Keep raw snapshots immutable and timestamp every ingestion.

### Inputs

- Official FPL player and Gameweek statistics
- Premier League fixtures and results
- Player position and club at the time of each match
- Minutes, starts, goals, assists, clean sheets, saves, bonus, cards, own goals, and points
- Rolling expected goals and expected assists, when a reproducible licensed source is available
- Team attacking and defensive strength calculated only from matches already played
- Upcoming fixture strength, home/away status, rest days, and schedule congestion
- Availability signals: recent minutes, starts, injuries, suspensions, transfers, and promoted-team status

Resolve player identity across seasons with stable IDs plus a reviewed name/team mapping. Never join only on display name.

## 3. Choose prediction targets

Start with two targets rather than one season-total label:

1. `points_next_6`: points over the next six Gameweeks, including zeros when unavailable.
2. `minutes_next_6`: minutes over the same horizon.

The six-Gameweek horizon makes fixtures and current role meaningful while remaining useful for draft ranking. Aggregate rolling six-week predictions into a season-long estimate, with greater weight on the opening portion of the schedule and explicit uncertainty.

Later, predict quantiles (`p10`, `p50`, `p90`) or use bootstrapping so injury and rotation risk are visible.

## 4. Engineer leakage-safe features

Every feature for Gameweek `t` must be knowable before its deadline.

- Rolling 3/6/12-match points, minutes, starts, goals, assists, clean sheets, saves, bonus
- Per-90 rates with minimum-minute smoothing
- Recent share of team minutes and starts
- Player age, position, and promoted/new-signing flags
- Team rolling goals for/against and expected performance
- Opponent strength and weighted fixture difficulty over the next six Gameweeks
- Days of rest and European/domestic cup congestion
- Prior-season performance with regression toward positional averages

Do not use end-of-season totals, future team strength, final league position, or data revised after the prediction date.

## 5. Train honest baselines and ML models

Establish simple baselines first:

- Previous-season points per match multiplied by expected minutes
- Position-average projection
- Rolling exponentially weighted points-per-90 projection

Then compare:

- Regularized linear regression
- Histogram gradient boosting
- LightGBM/XGBoost only if it clearly improves walk-forward performance

Use season/Gameweek walk-forward validation. For each fold, train only on dates before the validation period. Report MAE/RMSE, rank correlation, top-k precision, and calibration of prediction intervals. The model should beat the simple baseline in ranking useful players, not merely lower global error for low-minute players.

## 6. Convert projections into draft value

Raw projected points are not draft value. For every position, estimate a replacement player from the pool likely to remain undrafted or freely available in a four-manager league.

```text
value_over_replacement = projected_points - replacement_points_at_position
```

Then adjust for:

- Positional scarcity among remaining players
- Required open roster slots
- Playing-time floor and injury/rotation risk
- Early-season fixture strength
- Upside versus floor, depending on Classic or head-to-head scoring
- Correlation and concentration risk across one club

The replacement threshold must be recalculated as players leave the board.

## 7. Make recommendations live during the draft

Maintain a draft state containing:

- Every pick in order and the manager who made it
- Available-player set
- Your roster and remaining positional slots
- Current overall and positional rankings
- Number of selections before your next pick

After every pick:

1. Remove the selected player.
2. Recalculate replacement levels and scarcity.
3. Reject positions whose roster quota is full.
4. Estimate whether each candidate will survive to your next pick.
5. Recommend a primary choice plus two fallbacks and explain why.

The next major optimizer should simulate the other three managers. Begin with rank-biased stochastic picks constrained by their open roster positions. Later learn opponent tendencies from your league's own draft history. Compare "take now" value with the expected best roster after waiting one turn.

## 8. Test by replaying old drafts

Backtest at two levels:

- **Projection backtest:** Train before a past season and evaluate predictions through that season.
- **Draft replay:** Simulate four-manager snake drafts using only information available on draft day, then score resulting squads using actual later points.

Compare against auto-draft by last-season points, official draft rank where available, random position-valid drafting, and a projection-only strategy without scarcity.

Run many randomized draft orders and opponent strategies. Report mean result, downside, and sensitivity to draft slot.

## 9. Deliver in phases

### Phase 1 — usable baseline

- Historical data ingestion
- Leakage-safe table
- Baseline projection
- CSV rankings
- Manual live pick entry and dynamic recommendations

### Phase 2 — validated ML

- Walk-forward model comparison
- Uncertainty estimates
- Fixture/availability features
- Reproducible experiment reports

### Phase 3 — draft optimization

- Opponent simulations
- Player survival probability
- Full-roster Monte Carlo evaluation
- Strategy tuning for Classic versus head-to-head

### Phase 4 — draft-day interface

- Fast local web or terminal UI
- Search/autocomplete for picks
- Undo incorrect pick
- Primary recommendation with fallbacks
- Automatic state save after every selection

### Phase 5 — weekly roster management

- Rolling 1-, 3-, 6-Gameweek and rest-of-season forecasts
- Explainable role, threat, team, fixture, and availability trends
- Same-position waiver/free-agent add-drop optimizer
- Waiver priority ordering with fallback claims
- Breakout and sleeper alerts with uncertainty controls
- Two-sided trade evaluator and acceptance estimate
- Starting XI and bench-order recommendation before each deadline

## 10. Immediate next milestone

Collect and normalize historical Gameweek data, produce a leakage audit, and establish a walk-forward baseline before tuning a complex model. A sophisticated optimizer cannot rescue inaccurate projections.
