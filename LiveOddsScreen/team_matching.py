from typing import List, Dict, Any, Optional, Tuple

from rapidfuzz import fuzz


ALIASES = {
    "internazionale": "inter milan",
    "manchester united": "man united",
    "manchester city": "man city",
    "bayern munich": "bayern",
    "psg": "paris saint germain",
    "athletic bilbao": "athletic club",
    "real sociedad": "sociedad",
    "juventus": "juve",
    "roma": "as roma",
    "napoli": "ssc napoli",
    "sporting": "sporting cp",
    "porto": "fc porto",
    "benfica": "sl benfica",
    "sevilla": "fc sevilla",
    "betis": "real betis",
    # MLB abbreviations and common nicknames
    "chi cubs": "chicago cubs",
    "chi white sox": "chicago white sox",
    "reds": "cincinnati reds",
    "nats": "washington nationals",
    "mariners": "seattle mariners",
    "braves": "atlanta braves",
}


def normalize_team_name(raw: str) -> str:
    if not raw:
        return ""
    name = raw.lower().strip()
    replacements = [
        ("st.", "st"),
        ("fc ", ""),
        (" cf", ""),
        (" club", ""),
        ("basketball", ""),
        ("football", ""),
        ("baseball", ""),
        ("\u00a0", " "),
    ]
    for old, new in replacements:
        name = name.replace(old, new)
    name = " ".join(name.split())
    if name in ALIASES:
        name = ALIASES[name]
    return name


def fuzzy_score(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    a_n = normalize_team_name(a)
    b_n = normalize_team_name(b)
    return max(
        fuzz.token_sort_ratio(a_n, b_n),
        fuzz.token_set_ratio(a_n, b_n),
    ) / 100.0


def match_events(
    left_events: List[Dict[str, Any]],
    right_events: List[Dict[str, Any]],
    left_extract: Tuple[str, str] = ("home", "away"),
    right_extract: Tuple[str, str] = ("home", "away"),
    threshold: float = 0.78,
) -> List[Dict[str, Any]]:
    """Match left to right events using fuzzy team name matching.

    Each event is expected to carry home/away team fields. Field names are configurable via left_extract/right_extract.
    Returns a list of dicts with left, right, and match_score.
    """
    results: List[Dict[str, Any]] = []
    used_right = set()
    l_home_key, l_away_key = left_extract
    r_home_key, r_away_key = right_extract

    for l_event in left_events:
        l_home = l_event.get(l_home_key, "")
        l_away = l_event.get(l_away_key, "")
        best = None
        best_score = 0.0
        best_idx = -1
        for idx, r_event in enumerate(right_events):
            if idx in used_right:
                continue
            r_home = r_event.get(r_home_key, "")
            r_away = r_event.get(r_away_key, "")

            s1 = (fuzzy_score(l_home, r_home) + fuzzy_score(l_away, r_away)) / 2.0
            s2 = (fuzzy_score(l_home, r_away) + fuzzy_score(l_away, r_home)) / 2.0
            score = max(s1, s2)
            if score > best_score and score >= threshold:
                best_score = score
                best = r_event
                best_idx = idx
        if best is not None:
            used_right.add(best_idx)
            results.append({
                "left": l_event,
                "right": best,
                "match_score": round(best_score, 3),
            })
    return results

