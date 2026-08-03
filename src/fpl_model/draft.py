"""Live FPL Draft state and deterministic baseline recommendations."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

POSITIONS = ("GK", "DEF", "MID", "FWD")
ROSTER_LIMITS = {"GK": 2, "DEF": 5, "MID": 5, "FWD": 3}


@dataclass(frozen=True, slots=True)
class PlayerProjection:
    name: str
    position: str
    projected_points: float
    uncertainty: float = 0.0

    def __post_init__(self) -> None:
        if self.position not in POSITIONS:
            raise ValueError(f"Unknown position: {self.position}")
        if self.projected_points < 0 or self.uncertainty < 0:
            raise ValueError("Points and uncertainty must be non-negative")


@dataclass(frozen=True, slots=True)
class Recommendation:
    player: PlayerProjection
    replacement_points: float
    value_over_replacement: float
    scarcity_bonus: float
    risk_penalty: float
    score: float


class DraftBoard:
    """Track selections and recalculate recommendations after every pick."""

    def __init__(
        self,
        players: Iterable[PlayerProjection],
        *,
        manager_count: int = 4,
        my_roster: Iterable[str] = (),
    ) -> None:
        if manager_count < 2:
            raise ValueError("manager_count must be at least 2")
        player_list = list(players)
        names = [player.name for player in player_list]
        if len(names) != len(set(names)):
            raise ValueError("Player names must be unique")
        self.manager_count = manager_count
        self._available = {player.name: player for player in player_list}
        self._selected: list[str] = []
        self._my_roster: list[PlayerProjection] = []
        for name in my_roster:
            self.record_pick(name, mine=True)

    @property
    def selected(self) -> tuple[str, ...]:
        return tuple(self._selected)

    @property
    def my_roster(self) -> tuple[PlayerProjection, ...]:
        return tuple(self._my_roster)

    @property
    def available(self) -> tuple[PlayerProjection, ...]:
        return tuple(self._available.values())

    def record_pick(self, player_name: str, *, mine: bool = False) -> PlayerProjection:
        try:
            player = self._available.pop(player_name)
        except KeyError as error:
            raise ValueError(f"Player is unavailable or unknown: {player_name}") from error
        if mine and self.open_slots(player.position) <= 0:
            self._available[player_name] = player
            raise ValueError(f"Roster quota already full for {player.position}")
        self._selected.append(player_name)
        if mine:
            self._my_roster.append(player)
        return player

    def open_slots(self, position: str) -> int:
        if position not in POSITIONS:
            raise ValueError(f"Unknown position: {position}")
        counts = Counter(player.position for player in self._my_roster)
        return ROSTER_LIMITS[position] - counts[position]

    def replacement_points(self, position: str) -> float:
        remaining = sorted(
            (
                player.projected_points
                for player in self._available.values()
                if player.position == position
            ),
            reverse=True,
        )
        if not remaining:
            return 0.0
        league_demand = self.manager_count * ROSTER_LIMITS[position]
        return remaining[min(league_demand, len(remaining) - 1)]

    def recommendations(self, limit: int = 5) -> list[Recommendation]:
        if limit < 1:
            raise ValueError("limit must be positive")
        results: list[Recommendation] = []
        for player in self._available.values():
            if self.open_slots(player.position) <= 0:
                continue
            replacement = self.replacement_points(player.position)
            vorp = player.projected_points - replacement
            position_pool = sum(
                candidate.position == player.position for candidate in self._available.values()
            )
            scarcity = max(
                0.0, self.manager_count * ROSTER_LIMITS[player.position] - position_pool
            )
            scarcity_bonus = 0.25 * scarcity
            risk_penalty = 0.15 * player.uncertainty
            results.append(
                Recommendation(
                    player=player,
                    replacement_points=replacement,
                    value_over_replacement=vorp,
                    scarcity_bonus=scarcity_bonus,
                    risk_penalty=risk_penalty,
                    score=vorp + scarcity_bonus - risk_penalty,
                )
            )
        return sorted(
            results,
            key=lambda item: (item.score, item.player.projected_points),
            reverse=True,
        )[:limit]
