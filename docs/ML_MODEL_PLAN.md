# Machine-learning model plan

## Purpose and current foundation

This document owns the prediction and decision-modeling work for the 2026/27 official FPL Draft league. The confirmed setting is a four-manager Head-to-Head league with trades enabled, an unknown snake-draft slot, and an initial preference for reliable starters. Opponents must be treated as noisy people rather than perfectly rational ranking followers.

The repository already provides a useful foundation:

- `data/processed/modeling_table.csv` preserves the original 285,598-row ten-season v1 export.
- `data/processed/modeling_table_ml_v2.csv` contains 253,281 registered player-event rows from all ten seasons from 2016/17 through 2025/26, with the original file left unchanged.
- Each ML-v2 row contains rolling 3-, 6-, and 12-event player features, event-period team form, cutoff/source metadata, and one- and six-event targets.
- `src/fpl_model/modeling.py` contains a first `HistGradientBoostingRegressor` walk-forward scaffold.
- The current active-player recency baseline predicts that the next six event periods resemble the previous six. On ML-v2 its MAE is 8.336-9.240 points and its Spearman rank correlation is 0.295-0.415 across the ten seasons.
- The 2026/27 preseason output currently ranks 560 selectable players, but it is a prior-season shrinkage baseline rather than a trained forecast.

The objective is not to find the most complicated model. It is to produce calibrated weekly player distributions that improve actual draft, waiver, lineup, and trade decisions.

## Modeling architecture

Use a two-stage player model, followed by a decision optimizer.

### Stage 1: availability and minutes

Playing time should be forecast before points because it is the largest source of avoidable risk and directly reflects the reliable-starter preference.

For each player and future Gameweek, estimate:

1. probability of appearing;
2. probability of starting;
3. minutes conditional on appearing or starting; and
4. the resulting full distribution of minutes, including a point mass at zero.

The first implementation should use boosted-tree classifiers for appearance and start probability, plus a boosted-tree regressor for conditional minutes. A hurdle model is preferable to one regression over all minute totals because zero minutes and 60-90 minutes arise from different processes. Predictions must obey `P(start) <= P(appear)` and remain in the 0-90 range, aside from explicitly modeled extra-time competitions, which do not count as Premier League minutes.

Initial minutes features should extend the existing table with availability status at the cutoff, recent start and minutes shares, consecutive starts, substitution patterns, squad competition, rest, fixture congestion, transfer/new-signing status, and return-from-injury indicators. Until reliable injury and projected-lineup feeds exist, missing availability information must increase uncertainty rather than silently imply availability.

### Stage 2: fantasy points conditional on minutes

Predict points conditional on the Stage 1 minutes distribution. The first production candidate should be a boosted-tree model for points per appearance or points conditional on minutes, position, role, team strength, and opponent. Each simulated Gameweek should then combine:

```text
availability/start draw -> minutes draw -> conditional points draw
```

This decomposition prevents a prolific rotation player from being valued like a reliable 90-minute starter. It also permits transparent explanations such as "strong scoring rate, but only a 54% start probability."

The current six-Gameweek targets remain useful for benchmark continuity, but the preferred training unit is one future player-Gameweek. Weekly forecasts can then be summed through fixtures to produce 1-, 3-, and 6-Gameweek distributions. Rest-of-season estimates should be a schedule aggregation with increasing uncertainty, not a single long-horizon regression presented with false precision.

Position-specific effects are essential because points arise differently for goalkeepers, defenders, midfielders, and forwards. Start with position as a feature and report performance by position. Move to separate position models only if validation demonstrates a stable gain and each subset retains enough data.

## Candidate models

### Boosted trees: primary candidates

Use scikit-learn's histogram gradient boosting first because it is already in the project dependencies and current scaffold. Compare it with regularized linear/logistic models and the existing recency baseline. Add LightGBM or XGBoost only if it produces a repeatable temporal-validation improvement large enough to justify another dependency.

Boosted trees are the best first fit for the current data because it is medium-sized tabular data with nonlinear interactions, missing values, rolling form, position, and fixture effects. Tune shallowly and conservatively. The experiment budget should focus on feature validity, target construction, era handling, and calibration before extensive hyperparameter search.

### Bayesian candidates

Bayesian methods have two useful roles:

- hierarchical shrinkage for sparse players, promoted clubs, new signings, and small per-90 samples;
- sequential updating of opponent behavior as draft picks and weekly actions are observed.

A Bayesian or empirical-Bayes rate model can shrink goals, assists, bonus, saves, and clean-sheet contributions toward position/team priors. Its posterior can feed the boosted-tree model or act as a transparent challenger. A full Bayesian player-points model is optional and should be adopted only if its calibration or sparse-player performance beats simpler shrinkage plus boosted trees.

Bayesian probability and boosted trees are therefore complementary, not mutually exclusive: trees estimate player outcomes, while Bayesian updating handles sparse evidence and changing beliefs.

### Neural network: challenger only

Do not make a neural network the default with the current 253,281-row ML-v2 tabular table. Although ten seasons provide more rows, they do not provide ten seasons of one consistent modern schema. Test a neural model only after the leakage-safe tree pipeline, expected-minutes model, era controls, and calibrated intervals are established.

A neural model earns promotion only if it:

1. uses exactly the same cutoff-safe folds and features as the primary models;
2. improves the Head-to-Head decision metric and rank quality, not merely training loss;
3. shows improvement in at least three of four season holdouts, including 2025/26;
4. remains calibrated after correction and does not materially harm low-minute, promoted, or transferred-player groups;
5. is stable across seeds and modest hyperparameter changes; and
6. provides enough explainability and inference speed for live draft use.

Sequence models become more plausible later if several additional seasons, event-level histories, lineup context, and a clear missing-data treatment are available. Complexity alone is not evidence of better forecasting.

## Temporal validation and leakage controls

All model selection must simulate what was knowable before a real deadline.

### Purged rolling-origin validation

Use rolling-origin folds by season and Gameweek. For a validation cutoff at Gameweek `t`, features may include only snapshots created before the `t` deadline.

The current `walk_forward_validate` scaffold trains on every row with a Gameweek earlier than the validation Gameweek. That is not sufficient for `points_next_6` or `minutes_next_6`: a training row at `t-1` contains outcomes through `t+5`. For a six-week target, purge training labels whose outcome window touches the validation period. In practice, the final eligible training origin must be at least six Gameweeks before the validation origin, with an additional embargo if sources can be revised after publication.

For the preferred one-Gameweek target, train only on labels fully observed before the validation deadline. Hyperparameter tuning and interval calibration must be nested inside the training window; the validation fold cannot be reused for either.

### Schema eras and missing feature families

The ten-season table is not one homogeneous dataset. Older seasons lack modern expected-stat fields, and the current feature builder substitutes zero when a source column does not exist. That makes "not recorded" indistinguishable from a genuine zero unless availability is represented explicitly.

Create data-driven schema metadata before fitting:

- `schema_era`: categorical version derived from the set and definition of source fields available that season;
- `has_expected_stats_source`: whether expected goals/assists were recorded by the historical source for that row's season;
- `has_availability_source`, `has_fixture_strength_source`, and equivalent flags for each optional feature family;
- `season_recency`: seasons before the prediction season, retained for weighting and drift diagnostics;
- `disrupted_schedule`: explicit flag for seasons with materially altered scheduling, including 2019/20; and
- `event_sequence`: chronological event index derived from deadline or fixture chronology rather than raw Gameweek number.

Missing expected statistics should remain null until the modeling boundary, accompanied by their availability indicator. Compare native missing-value handling, training-era medians, and a reduced common-schema model. Never convert unavailable historical expected statistics to meaningful zeros without an indicator. An `xG = 0` observation means no expected goals; `has_expected_stats_source = 0` means the measurement was unavailable.

Use at least two feature sets in every model comparison:

1. **Common schema:** only variables reliably available across all ten seasons. This uses the full history and is the robustness reference.
2. **Modern schema:** includes expected and other newer statistics, trained only on seasons where those fields were genuinely recorded.

Optionally test a hybrid model in which the common-schema prediction is an input or prior and the modern features estimate a residual. Promote the hybrid only if it improves recent-season holdouts without producing an era artifact.

The 2019/20 source uses Gameweek numbering through 47. No split, rolling window, or future target may assume that a season ends at Gameweek 38 or that `gameweek + 1` is the next chronological event. Sort by actual deadline/fixture chronology where available and otherwise by a validated per-season event sequence. Define a six-Gameweek target as the next six FPL event periods in that sequence; separately count actual fixtures because blanks and doubles can produce zero or multiple matches.

### Recency weighting and season selection

More history reduces variance, but old seasons can introduce concept drift from rule, tactical, role, scheduling, and data-collection changes. Treat the choice of history as a model parameter, not an assumption.

Within the training portion of each outer temporal fold, compare:

- expanding all-history training;
- fixed windows of the most recent 3, 5, and 7 seasons; and
- all-history training with exponential season weights, initially testing half-lives of 2, 3, and 5 seasons.

Choose the window or decay only through nested temporal validation. The untouched latest-season test fold cannot choose it. Prefer the simplest choice whose recent-season performance is statistically indistinguishable from the best.

The expected default is a five-season or exponentially weighted primary model, with older 2016/17-2020/21 rows contributing mainly to stable relationships such as minutes-to-points and position effects. The all-ten-season common-schema model remains a challenger and variance check. Modern expected-stat models must use only their genuine availability era; sample weighting cannot repair a fabricated schema.

Report error and calibration by prediction season, schema era, and years of recency. If older rows improve aggregate MAE but harm 2024/25 or 2025/26 ranking/calibration, exclude or further downweight them for 2026/27 production.

### Season holdouts

Report expanding-season tests across the ten-season history, with particular weight on full 2024/25 and 2025/26 holdouts. The earliest seasons can supply training data, but promotion evidence should come mainly from recent unseen seasons. At minimum use:

- early expanding folds beginning with 2016/17-2018/19 to diagnose sample-size and era effects;
- train through 2022/23, validate 2023/24, and test 2024/25;
- then expand through 2024/25 and retain 2025/26 as the final recent holdout.

Within-season rolling tests are still required to measure adaptation after transfers, injuries, and manager changes.

### Leakage audit

Every generated feature should carry or inherit an `available_at` timestamp. The pipeline must fail when `available_at >= prediction_cutoff`. Specifically verify:

- rolling features use `shift(1)` before aggregation, as the current feature builder does;
- future targets never enter features, preprocessing, filtering, or imputation;
- scalers, encoders, priors, and replacement levels are fit only on the training window;
- current status and injury information reflects the historical cutoff, not today's corrected value;
- team strength uses only previously completed matches;
- transfers and positions reflect the player's club and position at the cutoff;
- unavailable source fields remain distinguishable from observed zeros through schema indicators;
- Gameweek order comes from validated event chronology, including the 47-number 2019/20 source, rather than a hard-coded 1-38 assumption;
- end-of-season totals, final standings, and same-Gameweek `xP` are excluded;
- duplicate-fixture Gameweeks aggregate correctly without leaking later matches; and
- player identity uses stable source codes rather than display-name joins.

Snapshot source hashes and experiment configuration with every model artifact so a ranking can be reproduced.

## Probabilistic forecasts and calibration

Every forecast should expose a distribution, not only an expected value.

For minutes, retain calibrated appearance and start probabilities plus minute quantiles. For points, initially fit quantile boosted-tree models for p10, p50, and p90, then compare with residual bootstrapping. Prevent quantile crossing by sorting or constrained post-processing.

Use out-of-fold conformal calibration on temporally later calibration windows to correct interval coverage. Measure:

- Brier score and reliability curves for appearance/start probabilities;
- MAE for expected minutes and points;
- pinball loss for each quantile;
- empirical coverage and width of the p10-p90 interval;
- calibration by position, minutes band, transfer/new-player status, and forecast horizon.

An 80% interval should contain approximately 80% of outcomes overall and should not conceal severe subgroup miscalibration. If subgroup samples are small, use wider pooled adjustments rather than claiming precise local calibration.

Weekly player samples are not independent. Later simulations should include shared fixture/team shocks and positive correlation between goalkeeper/defender clean sheets. Start with conservative residual resampling by position and fixture, then validate whether the extra correlation changes decisions materially.

## Head-to-Head objective

The decision objective is expected Head-to-Head wins, not raw season points. For each simulated Gameweek:

1. sample availability, minutes, and points for every relevant player;
2. choose each manager's legal starting lineup under FPL Draft rules;
3. apply autosub behavior and bench coverage;
4. compare weekly team scores; and
5. record win, draw, and loss probabilities.

Rank a roster or move primarily by expected match points or win probability over the relevant horizon. Because the user prefers reliable starters, break near-ties with downside protection: lineup availability, p10 weekly score, and reduced probability of fielding fewer than a full XI. Do not add a large arbitrary "safety" bonus that overwhelms expected scoring; estimate the value of reliability through simulations.

Draft evaluation should cover all four possible random slots. Weekly waiver and trade decisions should use the actual upcoming opponent and fixture horizon when known, while retaining six-week and rest-of-season value to avoid destructive short-term churn.

## Bayesian opponent updating

Begin with the stochastic mixture already defined in `configs/league.json`: rank-based picks, positional need, reaches, club/player preference, recency bias, and random choices. Give Friend A, B, and C broad shared priors because no past-season data is available.

For draft behavior, assign each manager mixture weights over these choice rules. A Dirichlet prior allows the weights to update after every observed pick. Within a rule, use a softmax choice model rather than assuming the top-ranked player is always selected. Maintain uncertainty so one surprising pick does not redefine a friend's profile.

Update separate behavior components over time:

- position and club preference from selections;
- reach tolerance from chosen rank relative to available rank;
- recency sensitivity from post-haul moves;
- waiver/free-agent activity from action frequency and timing;
- hold/drop patience from tenure after poor results;
- trade willingness and acceptance from offers and outcomes.

Simple Beta-Binomial or Dirichlet-Multinomial updates are sufficient initially. More complex hierarchical choice models should wait until the current season supplies enough observations. Opponent predictions must always return uncertainty and fallback branches.

## Monte Carlo decision optimization

### Live draft

At every pick, simulate the remainder of the snake draft thousands of times:

1. sample player outcome distributions;
2. sample each opponent's next choice from their posterior behavior model, constrained by open roster slots;
3. complete all four legal rosters;
4. simulate weekly Head-to-Head scoring; and
5. compare each candidate available now with waiting until the user's next turn.

Return the best current selection, two or more fallbacks, probability each target survives to the next pick, expected match-point gain, and downside. Recompute replacement value and positional scarcity after every recorded selection. Use common random numbers when comparing candidates so simulation noise does not reorder close choices.

### Waivers and free agents

For each legal same-position add/drop pair, simulate the current roster and changed roster over 1-, 3-, and 6-Gameweek horizons. Include claim probability, waiver priority, alternative claims, role uncertainty, and the option value of holding a roster spot. Optimize the ordered claim list rather than treating each claim independently.

### Trades

Simulate both managers before and after the complete proposed trade. Report change in Head-to-Head win probability, lineup availability, positional replacement value, and risk for each side. Estimate acceptance from the opponent posterior, but keep "good for our roster" separate from "likely to be accepted." A trade recommendation requires positive value after realistic replacement and lineup effects, not merely a higher sum of player means.

## Evaluation gates

No ML model should replace the current baseline merely because it has a lower aggregate error. Promotion requires all of the following:

1. **Leakage gate:** all labels are fully observed before validation; the six-Gameweek purge/embargo audit passes.
2. **Baseline gate:** median performance across season holdouts improves on the ML-v2 ten-season recency baseline (MAE 8.336-9.240 and Spearman 0.295-0.415), with no material regression in the recent 2024/25 or 2025/26 holdouts.
3. **Minutes gate:** appearance/start probabilities are calibrated and expected-minutes MAE beats recent-minutes and recent-start-rate baselines.
4. **Ranking gate:** improve Spearman plus draft-relevant NDCG/precision among the top available players and within each position.
5. **Uncertainty gate:** p10-p90 coverage is near its nominal 80% level overall and acceptable across the main position/minutes groups.
6. **Decision gate:** in historical four-manager draft replays across all draft slots and noisy opponent strategies, the model improves mean Head-to-Head results over recency auto-draft and projection-only drafting.
7. **Robustness gate:** gains persist across multiple seeds, reasonable hyperparameters, transferred/promoted-player exclusions, and alternative opponent-noise assumptions.

Use paired bootstrap intervals over Gameweeks or draft replays to distinguish a real gain from random variation. Publish negative results; a simpler model remains primary until evidence supports replacement.

## Phased implementation

### Phase ML-0: repair the experimental protocol

- Add purged rolling-origin split utilities for six-week labels.
- Add one-Gameweek targets for appearance, start, minutes, and points.
- Add chronological `event_sequence` handling so 2019/20 and future disrupted schedules do not assume 38 Gameweeks.
- Add schema-era and feature-family availability indicators before any missing-value imputation.
- Compare common-schema, modern-schema, and recency-window/weighting configurations inside nested temporal validation.
- Create an automated feature-timestamp/leakage audit.
- Expand reports beyond MAE to rank, probability, quantile, and subgroup metrics.

**Exit:** the existing recency baseline and current histogram-gradient-boosting scaffold run through the same reproducible, leakage-safe folds.

### Phase ML-1: reliable minutes model

- Build appearance and start classifiers.
- Build conditional-minutes regression and combine it into a zero-aware distribution.
- Calibrate probabilities on temporal calibration folds.
- Add historical availability, role, rest, and congestion features as sources permit.

**Exit:** the minutes system beats recent-start/minutes baselines and produces calibrated probabilities, especially for likely starters.

### Phase ML-2: conditional points model

- Train regularized linear and histogram-gradient-boosting candidates.
- Add empirical-Bayes rate shrinkage for small samples and new players.
- Produce 1-, 3-, and 6-Gameweek simulated distributions and rest-of-season aggregates.
- Generate explanations grouped into minutes, role, threat, team, fixture, and availability.

**Exit:** a promoted candidate passes leakage, baseline, ranking, uncertainty, and robustness gates.

### Phase ML-3: Head-to-Head draft optimizer

- Implement weekly roster scoring, legal lineups, and autosubs.
- Simulate all four draft slots and noisy opponent mixtures.
- Add survival-to-next-pick probability, fallbacks, and common-random-number comparisons.
- Replay historical drafts against recency, projection-only, and random legal strategies.

**Exit:** the optimizer improves simulated Head-to-Head results across draft slots without unacceptable downside.

### Phase ML-4: sequential opponent learning

- Persist current-season picks and transactions in SQLite.
- Update Friend A/B/C posteriors after each observed action.
- Calibrate pick survival, waiver-claim, and trade-acceptance probabilities.

**Exit:** opponent-aware simulations outperform broad shared priors in forward tests; otherwise retain the simpler shared model.

### Phase ML-5: weekly decisions and challengers

- Optimize waiver lists, free agents, lineups, and two-sided trades.
- Track prediction and decision outcomes every Gameweek.
- Retrain only on a scheduled, versioned cadence.
- Test LightGBM/XGBoost, richer Bayesian player models, and a neural-network challenger under the same promotion gates.

**Exit:** a reproducible weekly report states the recommendation, expected Head-to-Head impact, uncertainty, alternatives, and subsequent realized outcome.

## Immediate ML next step

Phase ML-0 now has a separately versioned table, chronological event sequencing, current-event and six-event targets, registration bounds, schema-era null handling, purged folds, and a serialized leakage audit with zero violations. Next, run the common-schema recency-window challengers and begin Phase ML-1 with appearance/start classifiers and conditional-minutes regression. Keep 2025/26 untouched as the final recent holdout while choosing windows and calibration settings inside earlier temporal folds.

### First Phase ML-1 result (2026-08-05)

The model-readiness gate produced `modeling_table_ml_v3.csv`. It excludes 320
Assistant Manager chip rows, canonicalizes 80 `GKP` aliases to `GK`, removes 10
equivalent duplicate source rows, and represents completed fixture exposure for
blank, single, double, and triple events. Its serialized audit has zero violations.

On the 2025/26 holdout, the calibrated appearance and start classifiers beat
smoothed recent-rate baselines on Brier score (0.0921 versus 0.1133, and 0.0873
versus 0.1120). Direct median, mean, and Poisson minutes challengers lost on the
pre-final folds. A baseline-anchored residual model won on both 2023/24 and
2024/25, was locked, and then beat the fixture-adjusted recent-minutes baseline
on 2025/26 MAE (11.624 versus 13.108). All three Phase ML-1 components therefore
pass their first baseline promotion gates. Next, add subgroup calibration and
begin the conditional-points model.

### First Phase ML-2 result (2026-08-06)

An absolute-error points residual was selected against a squared-error
challenger on 2023/24, confirmed on 2024/25, and evaluated on 2025/26. It beat
the recent-points baseline on all-row MAE in all three seasons. Among the
reliable-player cohort (recent expected minutes at least 45), 2025/26 MAE was
2.147 versus 2.554 and Spearman was 0.253 versus 0.200. This first challenger is
promoted for continued development, but the preseason board remains a separate
transparent shrinkage model because a new season has no within-season rolling
features yet.
