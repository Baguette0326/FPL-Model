/*
SSMS / SQL Server import for data/processed/modeling_table.csv.

1. Replace C:\FULL\PATH\TO\modeling_table.csv below with the absolute path.
2. The SQL Server service account must be able to read that file.
3. Run this script in the intended database. It recreates only the two objects below.
*/

IF OBJECT_ID('dbo.player_gameweeks', 'V') IS NOT NULL
    DROP VIEW dbo.player_gameweeks;
IF OBJECT_ID('dbo.player_gameweeks', 'U') IS NOT NULL
    DROP TABLE dbo.player_gameweeks;
IF OBJECT_ID('dbo.player_gameweeks_raw', 'U') IS NOT NULL
    DROP TABLE dbo.player_gameweeks_raw;

CREATE TABLE dbo.player_gameweeks_raw (
    event_sequence nvarchar(50) NULL,
    season nvarchar(50) NULL,
    gameweek nvarchar(50) NULL,
    player_code nvarchar(50) NULL,
    name nvarchar(150) NULL,
    position nvarchar(50) NULL,
    team nvarchar(150) NULL,
    expected_stats_available nvarchar(50) NULL,
    has_expected_stats_source nvarchar(50) NULL,
    has_availability_source nvarchar(50) NULL,
    has_fixture_strength_source nvarchar(50) NULL,
    schema_era nvarchar(50) NULL,
    disrupted_schedule nvarchar(50) NULL,
    total_points nvarchar(50) NULL,
    minutes nvarchar(50) NULL,
    starts nvarchar(50) NULL,
    goals_scored nvarchar(50) NULL,
    assists nvarchar(50) NULL,
    bonus nvarchar(50) NULL,
    clean_sheets nvarchar(50) NULL,
    saves nvarchar(50) NULL,
    yellow_cards nvarchar(50) NULL,
    red_cards nvarchar(50) NULL,
    expected_goals nvarchar(50) NULL,
    expected_assists nvarchar(50) NULL,
    prediction_cutoff nvarchar(50) NULL,
    available_at nvarchar(50) NULL,
    event_end_time nvarchar(50) NULL,
    points_last_3 nvarchar(50) NULL,
    points_last_6 nvarchar(50) NULL,
    points_last_12 nvarchar(50) NULL,
    minutes_last_3 nvarchar(50) NULL,
    minutes_last_6 nvarchar(50) NULL,
    minutes_last_12 nvarchar(50) NULL,
    starts_last_6 nvarchar(50) NULL,
    goals_scored_last_6 nvarchar(50) NULL,
    assists_last_6 nvarchar(50) NULL,
    bonus_last_6 nvarchar(50) NULL,
    expected_goals_last_6 nvarchar(50) NULL,
    expected_assists_last_6 nvarchar(50) NULL,
    points_next_6 nvarchar(50) NULL,
    minutes_next_6 nvarchar(50) NULL,
    appearance_next_1 nvarchar(50) NULL,
    start_next_1 nvarchar(50) NULL,
    minutes_next_1 nvarchar(50) NULL,
    points_next_1 nvarchar(50) NULL,
    target_1_observed_event nvarchar(50) NULL,
    target_6_observed_event nvarchar(50) NULL,
    season_recency nvarchar(50) NULL,
    team_goals_for_last_6 nvarchar(50) NULL,
    team_goals_against_last_6 nvarchar(50) NULL
);

BULK INSERT dbo.player_gameweeks_raw
FROM 'C:\FULL\PATH\TO\modeling_table.csv'
WITH (
    FORMAT = 'CSV',
    FIRSTROW = 2,
    FIELDQUOTE = '"',
    CODEPAGE = '65001',
    ROWTERMINATOR = '0x0a',
    TABLOCK
);

GO

CREATE VIEW dbo.player_gameweeks AS
SELECT
    TRY_CONVERT(int, NULLIF(event_sequence, '')) AS event_sequence,
    NULLIF(season, '') AS season,
    TRY_CONVERT(int, NULLIF(gameweek, '')) AS gameweek,
    TRY_CONVERT(bigint, TRY_CONVERT(decimal(20, 1), NULLIF(player_code, ''))) AS player_code,
    NULLIF(name, '') AS name,
    NULLIF(position, '') AS position,
    NULLIF(team, '') AS team,
    TRY_CONVERT(float, NULLIF(expected_stats_available, '')) AS expected_stats_available,
    TRY_CONVERT(float, NULLIF(has_expected_stats_source, '')) AS has_expected_stats_source,
    TRY_CONVERT(float, NULLIF(has_availability_source, '')) AS has_availability_source,
    TRY_CONVERT(float, NULLIF(has_fixture_strength_source, '')) AS has_fixture_strength_source,
    NULLIF(schema_era, '') AS schema_era,
    TRY_CONVERT(int, NULLIF(disrupted_schedule, '')) AS disrupted_schedule,
    TRY_CONVERT(float, NULLIF(total_points, '')) AS total_points,
    TRY_CONVERT(float, NULLIF(minutes, '')) AS minutes,
    TRY_CONVERT(float, NULLIF(starts, '')) AS starts,
    TRY_CONVERT(float, NULLIF(goals_scored, '')) AS goals_scored,
    TRY_CONVERT(float, NULLIF(assists, '')) AS assists,
    TRY_CONVERT(float, NULLIF(bonus, '')) AS bonus,
    TRY_CONVERT(float, NULLIF(clean_sheets, '')) AS clean_sheets,
    TRY_CONVERT(float, NULLIF(saves, '')) AS saves,
    TRY_CONVERT(float, NULLIF(yellow_cards, '')) AS yellow_cards,
    TRY_CONVERT(float, NULLIF(red_cards, '')) AS red_cards,
    TRY_CONVERT(float, NULLIF(expected_goals, '')) AS expected_goals,
    TRY_CONVERT(float, NULLIF(expected_assists, '')) AS expected_assists,
    TRY_CONVERT(datetimeoffset, NULLIF(prediction_cutoff, '')) AS prediction_cutoff,
    TRY_CONVERT(datetimeoffset, NULLIF(available_at, '')) AS available_at,
    TRY_CONVERT(datetimeoffset, NULLIF(event_end_time, '')) AS event_end_time,
    TRY_CONVERT(float, NULLIF(points_last_3, '')) AS points_last_3,
    TRY_CONVERT(float, NULLIF(points_last_6, '')) AS points_last_6,
    TRY_CONVERT(float, NULLIF(points_last_12, '')) AS points_last_12,
    TRY_CONVERT(float, NULLIF(minutes_last_3, '')) AS minutes_last_3,
    TRY_CONVERT(float, NULLIF(minutes_last_6, '')) AS minutes_last_6,
    TRY_CONVERT(float, NULLIF(minutes_last_12, '')) AS minutes_last_12,
    TRY_CONVERT(float, NULLIF(starts_last_6, '')) AS starts_last_6,
    TRY_CONVERT(float, NULLIF(goals_scored_last_6, '')) AS goals_scored_last_6,
    TRY_CONVERT(float, NULLIF(assists_last_6, '')) AS assists_last_6,
    TRY_CONVERT(float, NULLIF(bonus_last_6, '')) AS bonus_last_6,
    TRY_CONVERT(float, NULLIF(expected_goals_last_6, '')) AS expected_goals_last_6,
    TRY_CONVERT(float, NULLIF(expected_assists_last_6, '')) AS expected_assists_last_6,
    TRY_CONVERT(float, NULLIF(points_next_6, '')) AS points_next_6,
    TRY_CONVERT(float, NULLIF(minutes_next_6, '')) AS minutes_next_6,
    TRY_CONVERT(int, NULLIF(appearance_next_1, '')) AS appearance_next_1,
    TRY_CONVERT(int, NULLIF(start_next_1, '')) AS start_next_1,
    TRY_CONVERT(float, NULLIF(minutes_next_1, '')) AS minutes_next_1,
    TRY_CONVERT(float, NULLIF(points_next_1, '')) AS points_next_1,
    TRY_CONVERT(int, NULLIF(target_1_observed_event, '')) AS target_1_observed_event,
    TRY_CONVERT(int, NULLIF(target_6_observed_event, '')) AS target_6_observed_event,
    TRY_CONVERT(int, NULLIF(season_recency, '')) AS season_recency,
    TRY_CONVERT(float, NULLIF(team_goals_for_last_6, '')) AS team_goals_for_last_6,
    TRY_CONVERT(float, NULLIF(team_goals_against_last_6, '')) AS team_goals_against_last_6
FROM dbo.player_gameweeks_raw;

GO

SELECT COUNT(*) AS imported_rows FROM dbo.player_gameweeks_raw;
SELECT season, COUNT(*) AS rows
FROM dbo.player_gameweeks
GROUP BY season
ORDER BY season;
