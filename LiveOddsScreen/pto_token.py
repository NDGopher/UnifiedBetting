import re
from typing import Optional


def extract_pto_bearer_from_har(har_path: str = "LiveOddsScreen/PTOoddsScreen.har") -> Optional[str]:
    try:
        with open(har_path, "r", encoding="utf-8", errors="ignore") as f:
            data = f.read()
        # Try multiple patterns (escaped and unescaped) to find bearer token
        patterns = [
            r'authorization\s*[:=]\s*"bearer\s+([^"\s]+)"',
            r'authorization\\"\s*:\s*\\"bearer\s+([^\\"\s]+)\\"',
            r'Bearer\s+([A-Za-z0-9._\-]{20,})',
        ]
        for pat in patterns:
            m = re.search(pat, data, re.IGNORECASE)
            if m:
                return m.group(1)
    except Exception:
        pass
    return None

