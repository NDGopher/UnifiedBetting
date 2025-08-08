import json
from pathlib import Path
from typing import Optional, Tuple


def resolve_chrome_profile() -> Tuple[Optional[str], Optional[str]]:
    """Return (chrome_user_data_dir, chrome_profile_dir) by preferring
    LiveOddsScreen/config.json and falling back to backend/config.json pto section.
    """
    # 1) Try LiveOddsScreen/config.json
    local_cfg = Path("LiveOddsScreen/config.json")
    if local_cfg.exists():
        try:
            cfg = json.loads(local_cfg.read_text(encoding="utf-8"))
            cud = cfg.get("chrome_user_data_dir")
            cpd = cfg.get("chrome_profile_dir")
            if cud:
                return cud, cpd or "Default"
        except Exception:
            pass

    # 2) Fall back to backend/config.json -> pto
    backend_cfg = Path("backend/config.json")
    if backend_cfg.exists():
        try:
            cfg = json.loads(backend_cfg.read_text(encoding="utf-8"))
            pto = cfg.get("pto", {})
            cud = pto.get("chrome_user_data_dir")
            cpd = pto.get("chrome_profile_dir")
            if cud:
                return cud, cpd or "Default"
        except Exception:
            pass
    return None, None

