"""Command-line interface for live draft recommendations."""

from __future__ import annotations

import argparse

from .draft import DraftBoard
from .io import load_projections


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Four-manager FPL Draft assistant")
    subparsers = parser.add_subparsers(dest="command", required=True)
    recommend = subparsers.add_parser("recommend", help="Rank available draft picks")
    recommend.add_argument("--projections", required=True, help="Projection CSV path")
    recommend.add_argument("--taken", default="", help="Comma-separated opponent picks")
    recommend.add_argument("--mine", default="", help="Comma-separated picks on your roster")
    recommend.add_argument("--limit", type=int, default=5)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    board = DraftBoard(load_projections(args.projections))
    mine = [name.strip() for name in args.mine.split(",") if name.strip()]
    taken = [name.strip() for name in args.taken.split(",") if name.strip()]
    for name in mine:
        board.record_pick(name, mine=True)
    for name in taken:
        board.record_pick(name)

    print("rank  player                  pos  projection  VORP   score")
    for rank, item in enumerate(board.recommendations(args.limit), start=1):
        print(
            f"{rank:>4}  {item.player.name:<22}  {item.player.position:<3}  "
            f"{item.player.projected_points:>10.1f}  "
            f"{item.value_over_replacement:>5.1f}  {item.score:>6.1f}"
        )


if __name__ == "__main__":
    main()
