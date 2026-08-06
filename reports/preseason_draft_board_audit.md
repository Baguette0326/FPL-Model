# 2026/27 preseason draft-board audit

Generated from the official FPL snapshots refreshed on 2026-08-06 11:29 HKT.

- Players ranked: 563
- Duplicate stable player codes: 0
- Missing required draft-loader fields: 0
- Positions: 62 GK, 186 DEF, 249 MID, 66 FWD
- Manual-review players: 322
- Players without local Premier League history: 70
- Players on promoted clubs: 84
- Manual-review players in the top 60: 1

The only non-available player in the top 60 is James Garner (rank 38), listed
injured with an expected return of 22 August. He must be reviewed again before
the draft. New and promoted-player estimates use conservative priors and remain
manual-review candidates; none currently ranks inside the top 60.

## Reproducibility

- `bootstrap-static.json`: `986167479ef536dde02aa5637aa090f62f48503c0aef40ff2d587f11762ed744`
- `fixtures.json`: `9e7484118381f8202830906ba993c176475d8ca1796571f5dd78cbfc2d73bd3e`
- `2026-27_draft_rankings.csv`: `7be10f8890565eb19b336e52c63bf71fa7a073e0b54ce0df1d8d8bbce1c1365c`

The live recommendation CLI successfully loaded the real board and recalculated
fallbacks after Erling Haaland and Bruno Fernandes were marked as taken.
