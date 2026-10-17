import re

NORWEGIAN_CODES = {"no", "nb", "nn"}
WORD = re.compile(r"[a-zæøåA-ZÆØÅ]+")

# Words that are common in one language and absent or rare in the other.
# "for", "i", "as" and "by" are left out on purpose: they mean something in both.
NORWEGIAN_WORDS = {
    "og", "er", "det", "som", "på", "ikke", "vi", "har", "til", "med", "av", "fra", "om", "den",
    "kan", "våre", "vår", "oss", "over", "også", "hele", "ved", "eller", "være", "blir", "alle",
    "noe", "hos", "gjennom", "siden", "etter", "mellom", "bedrift", "selskap",
}
ENGLISH_WORDS = {
    "the", "and", "is", "are", "of", "in", "we", "our", "with", "that", "this", "from", "you",
    "have", "has", "on", "it", "be", "which", "was", "can", "all", "also", "across", "through",
    "company", "business", "since", "between",
}


def code_to_language(value: str | None) -> str:
    if not value:
        return "unknown"
    first = value.split(",")[0].strip().lower()
    primary = re.split(r"[-_]", first)[0]
    if primary in NORWEGIAN_CODES:
        return "no"
    if primary == "en":
        return "en"
    return "unknown"


def extract_html_lang(html: str, headers=None) -> str:
    """Read the language the page declares about itself: html lang, meta tags, then the header."""
    from selectolax.lexbor import LexborHTMLParser

    tree = LexborHTMLParser(html)
    candidates = []
    root = tree.css_first("html")
    if root is not None:
        candidates.append(root.attributes.get("lang"))
    meta = tree.css_first('meta[http-equiv="content-language" i]')
    if meta is not None:
        candidates.append(meta.attributes.get("content"))
    og = tree.css_first('meta[property="og:locale"]')
    if og is not None:
        candidates.append(og.attributes.get("content"))
    if headers:
        lowered = {key.lower(): value for key, value in headers.items()}
        candidates.append(lowered.get("content-language"))

    for value in candidates:
        language = code_to_language(value)
        if language != "unknown":
            return language
    return "unknown"


def guess_language(text: str) -> str:
    """Count stop words. Needs at least two hits and a clear winner, otherwise 'unknown'."""
    words = [word.lower() for word in WORD.findall(text)]
    norwegian = sum(1 for word in words if word in NORWEGIAN_WORDS)
    english = sum(1 for word in words if word in ENGLISH_WORDS)
    if max(norwegian, english) < 2 or norwegian == english:
        return "unknown"
    return "no" if norwegian > english else "en"


def detect_language(html: str, headers, text: str) -> str:
    """Page language saved with a snapshot. The text wins over a wrong tag (many sites
    ship lang="en" by default); the tag is used when the text is too short to judge."""
    guessed = guess_language(text)
    if guessed != "unknown":
        return guessed
    return extract_html_lang(html, headers)
