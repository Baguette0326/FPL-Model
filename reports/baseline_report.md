# Baseline report

This report is generated from real historical FPL data. The model is deliberately simple: the evaluation predicts that the next six Gameweeks resemble the previous six for players with at least 180 minutes in the prior six, while the preseason ranking regresses 2025/26 totals toward positional priors and applies a small opening-fixture adjustment.

## Walk-forward recency baseline

| Season | Rows | MAE | RMSE | Spearman rank correlation |
|---|---:|---:|---:|---:|
| 2016-17 | 7,450 | 8.662 | 11.179 | 0.344 |
| 2017-18 | 7,714 | 8.601 | 11.096 | 0.328 |
| 2018-19 | 7,511 | 8.428 | 10.840 | 0.378 |
| 2019-20 | 7,525 | 8.446 | 10.975 | 0.390 |
| 2020-21 | 7,548 | 9.017 | 11.683 | 0.351 |
| 2021-22 | 7,403 | 8.907 | 11.613 | 0.332 |
| 2022-23 | 7,422 | 8.808 | 11.342 | 0.352 |
| 2023-24 | 7,468 | 8.757 | 11.455 | 0.358 |
| 2024-25 | 7,538 | 8.336 | 11.003 | 0.415 |
| 2025-26 | 7,514 | 9.240 | 11.811 | 0.295 |

## Top 20 preliminary 2026/27 projections

These are baseline estimates, not final draft recommendations. Transfers, injuries, expected minutes, promoted players, and model uncertainty still require further work.

| Rank | Player | Pos | Club | Projected points | Uncertainty | Prior minutes | First-6 FDR |
|---:|---|---|---|---:|---:|---:|---:|
| 1 | Erling Haaland | FWD | Man City | 213.4 | 32.0 | 2,953 | 3.00 |
| 2 | Bruno Borges Fernandes | MID | Man Utd | 206.0 | 30.9 | 3,065 | 2.83 |
| 3 | Gabriel dos Santos Magalhães | DEF | Arsenal | 186.2 | 27.9 | 2,750 | 3.00 |
| 4 | Antoine Semenyo | MID | Man City | 178.2 | 26.7 | 3,200 | 3.00 |
| 5 | Morgan Gibbs-White | MID | Nott'm Forest | 167.0 | 25.1 | 3,101 | 3.00 |
| 6 | Igor Thiago Nascimento Rodrigues | FWD | Brentford | 165.9 | 24.9 | 3,282 | 3.17 |
| 7 | João Pedro Junqueira de Jesus | FWD | Chelsea | 163.8 | 24.6 | 2,658 | 3.00 |
| 8 | Declan Rice | MID | Arsenal | 163.8 | 24.6 | 3,093 | 3.00 |
| 9 | Marc Guéhi | DEF | Man City | 162.2 | 24.3 | 3,150 | 3.00 |
| 10 | Elliot Anderson | MID | Man City | 160.6 | 24.1 | 3,332 | 3.00 |
| 11 | Virgil van Dijk | DEF | Liverpool | 160.1 | 24.0 | 3,420 | 2.83 |
| 12 | Marcos Senesi Barón | DEF | Spurs | 159.0 | 23.8 | 3,288 | 3.00 |
| 13 | James Tarkowski | DEF | Everton | 156.0 | 23.4 | 3,330 | 2.83 |
| 14 | Ollie Watkins | FWD | Aston Villa | 155.8 | 23.4 | 2,833 | 3.00 |
| 15 | David Raya Martín | GK | Arsenal | 153.6 | 23.0 | 3,330 | 3.00 |
| 16 | Morgan Rogers | MID | Chelsea | 151.8 | 22.8 | 3,280 | 3.00 |
| 17 | Harry Wilson | MID | Leeds | 150.0 | 22.5 | 2,674 | 3.17 |
| 18 | Nico O'Reilly | DEF | Man City | 147.0 | 22.1 | 2,643 | 3.00 |
| 19 | Adrien Truffert | DEF | Bournemouth | 147.0 | 22.0 | 3,378 | 3.67 |
| 20 | Dominik Szoboszlai | MID | Liverpool | 145.6 | 21.8 | 3,232 | 2.83 |
