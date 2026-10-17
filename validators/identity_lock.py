import re
from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import urlsplit

from agent_engine.url_guard import is_official_host

DOMAIN_POINTS = Decimal("0.6")
ORGNR_POINTS = Decimal("0.25")
NAME_TOWN_POINTS = Decimal("0.15")


@dataclass(frozen=True)
class Identity:
    score: Decimal
    g: int
    domain_ok: bool
    orgnr_on_page: bool
    name_and_town_on_page: bool


def orgnr_pattern(orgnr: str) -> re.Pattern:
    groups = [orgnr[0:3], orgnr[3:6], orgnr[6:9]]
    return re.compile(r"(?<!\d)" + r"[ .]?".join(groups) + r"(?!\d)")


def contains_phrase(text: str, phrase: str | None) -> bool:
    if not phrase or not phrase.strip():
        return False
    words = [re.escape(word) for word in phrase.casefold().split()]
    return re.search(r"(?<!\w)" + r"\s+".join(words) + r"(?!\w)", text.casefold()) is not None


def check_identity(page_url: str, text: str, *, official_domain: str | None, orgnr: str,
                   legal_name: str | None, town: str | None,
                   threshold: Decimal = Decimal("0.6")) -> Identity:
    """Page-level identity score. G is 1 only when the page is on the official domain AND shows
    the organisation number or the legal name together with the town."""
    domain_ok = is_official_host(urlsplit(page_url).hostname, official_domain)
    orgnr_found = orgnr_pattern(orgnr).search(text) is not None
    name_town = contains_phrase(text, legal_name) and contains_phrase(text, town)

    score = Decimal("0")
    if domain_ok:
        score += DOMAIN_POINTS
    if orgnr_found:
        score += ORGNR_POINTS
    if name_town:
        score += NAME_TOWN_POINTS
    g = 1 if domain_ok and (orgnr_found or name_town) and score >= threshold else 0
    return Identity(score, g, domain_ok, orgnr_found, name_town)
