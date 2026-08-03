# League-specific strategy

## Confirmed settings

- Four managers
- Official FPL Draft
- Head-to-Head scoring
- Random draft order, currently unknown
- Trades enabled
- Draft expected next week after transfer news settles
- Initial preference for reliable starters

## Head-to-Head objective

The optimizer should not maximize only season-total points. It should value the probability of winning each Gameweek, which increases the importance of:

- Reliable starts and minutes
- A stable weekly scoring floor
- Fixture timing and short runs of favourable opponents
- Bench coverage for rotation and injury
- Selective upside without concentrating too much risk in one week

The first objective will combine expected weekly points, downside protection, and lineup availability. Once backtesting is available, the final metric will be simulated Head-to-Head wins rather than raw points alone.

## Opponent behavior

Other managers will not be treated as perfectly rational ranking followers. The initial simulator will sample from a mixture of behaviours:

- Mostly rank-based choices
- Positional need
- Early reaches
- Favourite-player or club bias
- Recency bias
- Random/noisy choices

When past league details are supplied, each manager can receive separate parameters for draft reaches, preferred positions/clubs, waiver activity, free-agent speed, trade willingness, and acceptance thresholds.

Opponent predictions should always remain probabilistic. The assistant should return robust fallback choices rather than pretending it knows another manager's next action with certainty.

## Pending information

Before the draft, request:

1. Exact date and time
2. Draft position after the random draw
3. Past draft order, squads, and final results
4. Any available waiver, free-agent, or trade history
