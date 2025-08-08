import argparse
import json
from typing import Any, Dict, List

from rich import print
from rich.table import Table

from betbck_live_dom_scraper import scrape_betbck_live, SiteSelectors
from pto_live_dom_scraper import scrape_pto_live, PTOSelectors
from team_matching import match_events


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def to_site_selectors(sel: Dict[str, Any]) -> SiteSelectors:
    return SiteSelectors(
        iframe_selector=sel["iframe_selector"],
        event_row_selector=sel["event_row_selector"],
        home_team_selector=sel["home_team_selector"],
        away_team_selector=sel["away_team_selector"],
        market_container_selector=sel.get("market_container_selector"),
        price_selector=sel.get("price_selector"),
    )


def to_pto_selectors(sel: Dict[str, Any]) -> PTOSelectors:
    return PTOSelectors(
        event_row_selector=sel["event_row_selector"],
        home_team_selector=sel["home_team_selector"],
        away_team_selector=sel["away_team_selector"],
        market_container_selector=sel.get("market_container_selector"),
        price_selector=sel.get("price_selector"),
    )


def render_matches(matches: List[Dict[str, Any]]):
    table = Table(title="Live Odds Matches")
    table.add_column("Home (BCK)")
    table.add_column("Away (BCK)")
    table.add_column("Home (PTO)")
    table.add_column("Away (PTO)")
    table.add_column("Score")
    for m in matches:
        b = m["left"]
        p = m["right"]
        table.add_row(
            b.get("home", ""),
            b.get("away", ""),
            p.get("home", ""),
            p.get("away", ""),
            str(m.get("match_score", 0)),
        )
    print(table)


def main():
    parser = argparse.ArgumentParser(description="Compare BetBCK live odds to PTO live odds via DOM scraping")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--selectors", default="selectors.json")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    cfg = load_json(args.config)
    sels = load_json(args.selectors)

    bck_cfg = sels["betbck"]
    pto_cfg = sels["pto"]

    user_data_dir = cfg.get("chrome_user_data_dir")
    profile_dir = cfg.get("chrome_profile_dir")

    print("[bold]Scraping BetBCK live...[/bold]")
    bck_events = scrape_betbck_live(
        live_url=bck_cfg["url"],
        selectors=to_site_selectors(bck_cfg),
        user_data_dir=user_data_dir,
        profile_dir=profile_dir,
    )
    print(f"Found BetBCK events: {len(bck_events)}")

    print("[bold]Scraping PTO live...[/bold]")
    pto_events = scrape_pto_live(
        pto_url=pto_cfg["url"],
        selectors=to_pto_selectors(pto_cfg),
        user_data_dir=user_data_dir,
        profile_dir=profile_dir,
    )
    print(f"Found PTO events: {len(pto_events)}")

    print("[bold]Matching events...[/bold]")
    matches = match_events(bck_events, pto_events)
    render_matches(matches)

    if args.debug:
        print("[bold]\nSample BetBCK event:[/bold]", bck_events[:1])
        print("[bold]\nSample PTO event:[/bold]", pto_events[:1])


if __name__ == "__main__":
    main()

