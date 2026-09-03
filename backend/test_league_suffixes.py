#!/usr/bin/env python3
"""POD league-suffix stripping: NCAA FCS must not leak into BetBCK search terms."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.pod_utils import (
    clean_pod_team_name_for_search,
    determine_betbck_search_term,
    normalize_team_name_for_matching,
    pick_betbck_search_token,
    strip_pod_league_suffix,
    strip_team_name_for_display,
)


def test_campbell_ncaa_fcs_strips_to_campbell():
    raw = "CampbellNCAA FCS"
    assert strip_pod_league_suffix(raw) == "Campbell"
    assert strip_team_name_for_display(raw) == "Campbell"
    assert clean_pod_team_name_for_search(raw) == "campbell"


def test_east_tennessee_state_unchanged():
    raw = "East Tennessee State"
    assert strip_pod_league_suffix(raw) == raw
    assert "tennessee" in clean_pod_team_name_for_search(raw)


def test_existing_ncaa_football_still_strips():
    assert strip_pod_league_suffix("AlabamaNCAA Football") == "Alabama"


def test_existing_nfl_preseason_still_strips():
    assert strip_pod_league_suffix("Dallas CowboysNFL Pre Season") == "Dallas Cowboys"


def test_existing_nba_abbrev_still_strips():
    assert strip_pod_league_suffix("New York KnicksNBA") == "New York Knicks"


def test_ncaa_fcs_does_not_leave_ncaa_glued():
    cleaned = clean_pod_team_name_for_search("Montana StateNCAA FCS")
    assert "ncaa" not in cleaned
    assert "fcs" not in cleaned
    assert cleaned == "montana state"


def test_unlv_bare_ncaa_suffix_strips():
    raw = "UNLVNCAA"
    assert strip_pod_league_suffix(raw) == "UNLV"
    assert strip_team_name_for_display(raw) == "UNLV"
    assert clean_pod_team_name_for_search(raw) == "unlv"


def test_ncaaf_ncaab_still_strip_before_bare_ncaa():
    assert strip_pod_league_suffix("GeorgiaNCAAF") == "Georgia"
    assert strip_pod_league_suffix("DukeNCAAB") == "Duke"


def test_new_mexico_is_not_chopped_to_new():
    for raw in ("New Mexico", "NewMexico", "NewMexicoNCAA", "New MexicoNCAA"):
        stripped = strip_pod_league_suffix(raw)
        assert "mexico" in stripped.lower(), raw
        assert stripped.lower() != "new", raw
        assert "mexico" in normalize_team_name_for_matching(raw)
        assert normalize_team_name_for_matching(raw) != "new"
        display = strip_team_name_for_display(raw)
        assert "mexico" in display.lower(), raw
        assert display.lower() != "new", raw


def test_soccer_mexico_suffix_still_strips():
    assert strip_pod_league_suffix("AtlasMexico") == "Atlas"
    assert "mexico" not in normalize_team_name_for_matching("AtlasMexico")


def test_search_term_uses_mexico_not_new():
    term = determine_betbck_search_term("New Mexico", "Central Michigan")
    if isinstance(term, tuple):
        term = term[0]
    assert term.lower() == "mexico"
    assert pick_betbck_search_token("new") == ""
    assert pick_betbck_search_token("central michigan").lower() == "michigan"


def main():
    tests = [
        test_campbell_ncaa_fcs_strips_to_campbell,
        test_east_tennessee_state_unchanged,
        test_existing_ncaa_football_still_strips,
        test_existing_nfl_preseason_still_strips,
        test_existing_nba_abbrev_still_strips,
        test_ncaa_fcs_does_not_leave_ncaa_glued,
        test_unlv_bare_ncaa_suffix_strips,
        test_ncaaf_ncaab_still_strip_before_bare_ncaa,
        test_new_mexico_is_not_chopped_to_new,
        test_soccer_mexico_suffix_still_strips,
        test_search_term_uses_mexico_not_new,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {fn.__name__}: {exc}")
            import traceback
            traceback.print_exc()
    if failed:
        raise SystemExit(1)
    print(f"OK {len(tests)} tests")


if __name__ == "__main__":
    main()
