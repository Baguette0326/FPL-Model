"""Weekly waiver and free-agent decision support for FPL Draft."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .draft import PlayerProjection


@dataclass(frozen=True, slots=True)
class WeeklyProjection:
    player: PlayerProjection
    points_next_3: float
    points_next_6: float
    rest_of_season_points: float
    minutes_trend: float = 0.0
    involvement_trend: float = 0.0

    @property
    def hold_value(self) -> float:
        """Balance immediate fixtures with longer-term value and emerging role."""
        trend_bonus = 0.75 * self.minutes_trend + 0.5 * self.involvement_trend
        risk_penalty = 0.1 * self.player.uncertainty
        return (
            0.45 * self.points_next_3
            + 0.35 * self.points_next_6
            + 0.20 * self.rest_of_season_points
            + trend_bonus
            - risk_penalty
        )


@dataclass(frozen=True, slots=True)
class WaiverRecommendation:
    add: WeeklyProjection
    drop: WeeklyProjection
    expected_gain: float
    breakout_score: float


def recommend_waivers(
    roster: Iterable[WeeklyProjection],
    free_agents: Iterable[WeeklyProjection],
    *,
    limit: int = 5,
) -> list[WaiverRecommendation]:
    """Recommend legal same-position add/drop pairs, best expected gain first."""
    if limit < 1:
        raise ValueError("limit must be positive")
    roster_list = list(roster)
    recommendations: list[WaiverRecommendation] = []
    for candidate in free_agents:
        same_position = [
            owned for owned in roster_list if owned.player.position == candidate.player.position
        ]
        if not same_position:
            continue
        drop = min(same_position, key=lambda owned: owned.hold_value)
        gain = candidate.hold_value - drop.hold_value
        breakout = candidate.minutes_trend + candidate.involvement_trend
        if gain > 0:
            recommendations.append(
                WaiverRecommendation(
                    add=candidate,
                    drop=drop,
                    expected_gain=gain,
                    breakout_score=breakout,
                )
            )
    return sorted(
        recommendations,
        key=lambda item: (item.expected_gain, item.breakout_score),
        reverse=True,
    )[:limit]
