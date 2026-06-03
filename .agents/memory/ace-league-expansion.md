---
name: Ace scraper league expansion
description: WT parameter and league ID strategy for action23.ag scraper
---

## Rule
Use `WT=1` for both `CreateSports.aspx` and `NewScheduleHelper.aspx` requests.
Use `WT=1` for the `ActiveLeaguesHelper.aspx` call too.
The Referer header must also reference `WT=1` to appear consistent.

**Why:** `WT=0` caused the schedule endpoint to return no games. The site uses WT=1 for the "today/upcoming" wager type.

## ActiveLeaguesHelper
`ActiveLeaguesHelper.aspx?WT=1` may return an empty body (HTTP 200 but no JSON).
In that case fall back to the full `_KNOWN_LEAGUE_IDS` list (currently 70 leagues).
The session-cached 28 IDs from the CreateSports response are also preserved as a secondary fallback.

## How to apply
Any time you add or modify endpoints on action23.ag, default to WT=1.
If the API response count drops unexpectedly, check the WT parameter first.
