from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class MarketPrice:
    label: str
    price: str


@dataclass
class EventOdds:
    sport: str
    market: str  # e.g., moneyline, spread, total
    home: str
    away: str
    # book -> {"home": price, "away": price}
    books: Dict[str, Dict[str, Optional[str]]] = field(default_factory=dict)

    def best_side(self) -> Dict[str, Optional[str]]:
        # Determine which book has the best price for each side (home/away) in American odds
        def parse_american(odd: Optional[str]) -> Optional[int]:
            if odd is None:
                return None
            try:
                s = odd.replace("+", "").strip()
                return int(s) if odd.startswith("-") is False else -int(s)
            except Exception:
                try:
                    return int(odd)
                except Exception:
                    return None

        best = {"home": None, "away": None}
        best_vals = {"home": None, "away": None}
        for book, sides in self.books.items():
            for side in ("home", "away"):
                v = parse_american(sides.get(side))
                if v is None:
                    continue
                # Higher positive is better for underdogs, and less negative is better for favorites
                # We maximize the numeric value where positives are naturally larger; for negatives, -110 > -120
                if best_vals[side] is None or v > best_vals[side]:
                    best_vals[side] = v
                    best[side] = book
        return best

    def best_side_with_value(self) -> Dict[str, Optional[str]]:
        # Returns formatted "Book Price" per side where available
        def parse_value(odd: Optional[str]) -> Optional[int]:
            if odd is None:
                return None
            try:
                if odd.startswith("+"):
                    return int(odd[1:])
                return int(odd)
            except Exception:
                return None

        result = {"home": None, "away": None}
        for side in ("home", "away"):
            best_book = None
            best_numeric = None
            best_price_str = None
            for book, sides in self.books.items():
                val = parse_value(sides.get(side))
                if val is None:
                    continue
                if best_numeric is None or val > best_numeric:
                    best_numeric = val
                    best_book = book
                    best_price_str = sides.get(side)
            if best_book and best_price_str is not None:
                result[side] = f"{best_book} {best_price_str}"
        return result

    def average_odds(self) -> Dict[str, Optional[float]]:
        def parse(odd: Optional[str]) -> Optional[int]:
            if odd is None:
                return None
            try:
                if odd.startswith("+"):
                    return int(odd[1:])
                return int(odd)
            except Exception:
                return None
        agg = {"home": [], "away": []}
        for _, sides in self.books.items():
            for side in ("home", "away"):
                v = parse(sides.get(side))
                if v is not None:
                    agg[side].append(v)
        return {
            "home": (sum(agg["home"]) / len(agg["home"])) if agg["home"] else None,
            "away": (sum(agg["away"]) / len(agg["away"])) if agg["away"] else None,
        }

