import re
from typing import Optional


def extract_gsid_from_har(har_path: str = "LiveOddsScreen/livebetting.har") -> Optional[str]:
    try:
        with open(har_path, "r", encoding="utf-8", errors="ignore") as f:
            data = f.read()
        m = re.search(r"gsid=([a-z0-9]+)", data, re.IGNORECASE)
        if m:
            return m.group(1)
    except Exception:
        pass
    return None

