"""
Single source-of-truth for all league / promotion suffixes that POD
concatenates directly onto fighter and team names without a space separator.

Import from here instead of maintaining separate copies in pod_utils.py and
main.py.  Adding a new promotion or league to either list here propagates
automatically to every caller.

Three tools are provided:
  MULTIWORD_SUFFIXES  – multi-word promotions/leagues glued to names
  LEAGUE_ABBREVS      – all-caps abbreviations glued to names
  MMA_PROMOTION_ABBREV_RE – regex fallback for any 2-6 char all-caps suffix
                            directly appended (no space) to a name; catches
                            new promotions without requiring per-entry updates
"""

import re

# ---------------------------------------------------------------------------
# Multi-word league / promotion names POD concatenates without a space
# e.g. "Montreal AlouettesCanadian Football" → "Montreal Alouettes"
#      "Jon JonesCage Warriors"              → "Jon Jones"
# ---------------------------------------------------------------------------
MULTIWORD_SUFFIXES: tuple = (
    'Canadian Football',
    'Arena Football',
    'Major League Soccer',
    'Major League Baseball',
    'National Football League',
    'National Basketball Association',
    'National Hockey League',
    # NCAA sport suffixes
    'NCAA Baseball',
    'NCAA Football',
    'NCAA Basketball',
    'NCAA Softball',
    'NCAA Soccer',
    'NCAA Volleyball',
    'NCAA Hockey',
    'NCAA Lacrosse',
    # International / friendly suffixes
    'International',
    'Friendlies',
    'Friendly',
    'Club Friendlies Women',
    'Club Friendlies',
    # MMA / combat sport promotions (multi-word)
    'Cage Warriors',
    'Bellator MMA',
    'Bellator',
    'Glory Kickboxing',
    'Bare Knuckle Fighting Championship',
    # NBA development / summer leagues POD concatenates directly onto team names
    # e.g. "Atlanta HawksNBA Summer League" → "Atlanta Hawks"
    'NBA Summer League',
    'NBA G League',
    'G League',
    'Summer League',
)

# ---------------------------------------------------------------------------
# All-caps abbreviations POD concatenates without a space
# e.g. "New York KnicksNBA" → "New York Knicks"
#      "Jon JonesUFC"       → "Jon Jones"
# ---------------------------------------------------------------------------
LEAGUE_ABBREVS: tuple = (
    # Major North-American leagues
    'WNBA', 'NBA', 'NFL', 'NHL', 'MLB', 'MLS', 'NWSL', 'PWHL',
    'NCAAF', 'NCAAB',
    'AFL', 'CFL', 'XFL', 'USFL',
    # MMA / combat sports (known abbreviations — new ones are handled by the
    # regex fallback below so you don't need to add every promotion here)
    'UFC', 'PFL', 'BKFC', 'ONE', 'RIZIN', 'LFA', 'CFFC', 'ACB', 'KSW',
    'ACA', 'M1', 'RCC', 'AMC', 'FNG', 'WSOF', 'BRAVE', 'GLORY', 'BOHC',
    # Soccer confederations / bodies
    'UEFA', 'CONMEBOL', 'CONCACAF', 'AFC', 'OFC', 'FIFA', 'CAF',
)

# ---------------------------------------------------------------------------
# Regex fallback — catches ANY 2-6 char all-caps abbreviation that is glued
# directly to a name (preceded immediately by a lowercase letter, no space).
#
# Why this helps: MMA/combat promotions almost always use short all-caps
# identifiers (PFL, BKFC, ONE, RIZIN, LFA …). When POD adds a brand-new
# promotion we haven't listed above, its abbreviation will still be stripped
# by this pattern without any code change.
#
# Examples:
#   "Jon JonesNEWPROMO"   → "Jon Jones"
#   "Khamzat ChibaevXYZ"  → "Khamzat Chibaev"
#
# False-positive guard: the lookbehind `(?<=[a-z])` ensures the abbreviation
# is glued to a lowercase letter, so space-separated names ("Team ONE") and
# names that are already all-caps ("LAFC") are left alone.
# ---------------------------------------------------------------------------
MMA_PROMOTION_ABBREV_RE: re.Pattern = re.compile(r'(?<=[a-z])[A-Z]{2,8}$')


def strip_mma_suffix(name: str) -> str:
    """Strip a directly-appended MMA promotion suffix from *name*.

    Applies MULTIWORD_SUFFIXES, LEAGUE_ABBREVS, and the MMA_PROMOTION_ABBREV_RE
    regex fallback in sequence.  Returns the cleaned name (unchanged if no
    suffix was found).

    This is the canonical stripping routine for fighter names. Team-name
    stripping in pod_utils.strip_pod_league_suffix uses the same constants
    but also handles country codes and other soccer-specific patterns.
    """
    if not name:
        return name

    # 1. Multi-word suffixes
    for mw in MULTIWORD_SUFFIXES:
        if name.endswith(mw) and len(name) > len(mw):
            preceding = name[-(len(mw) + 1):-(len(mw))]
            if preceding.isalpha():
                name = name[:-len(mw)].strip()
                return name  # one suffix at a time

    # 2. Known all-caps abbreviations
    for abbrev in LEAGUE_ABBREVS:
        if name.endswith(abbrev) and len(name) > len(abbrev):
            preceding_char = name[-(len(abbrev) + 1):-(len(abbrev))]
            if preceding_char.rstrip() != '':
                name = name[:-len(abbrev)].strip()
                return name

    # 3. Regex fallback — any unknown 2-6 char all-caps abbreviation glued
    #    directly to the end of the name (preceded by a lowercase letter)
    m = MMA_PROMOTION_ABBREV_RE.search(name)
    if m:
        name = name[:m.start()].strip()

    return name
