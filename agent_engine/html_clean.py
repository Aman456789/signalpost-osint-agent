import re
from dataclasses import dataclass

import trafilatura
from selectolax.lexbor import LexborHTMLParser

from agent_engine.language import detect_language
from storage.evidence_vault import normalise_text

IDENTITY_TEXT_CHARS = 20000
HIDDEN_TAGS = ("script", "style", "noscript", "template", "svg", "iframe")
HIDDEN_SELECTOR = ", ".join(HIDDEN_TAGS) + ', [hidden], [aria-hidden="true"], [style]'
BOILERPLATE_SELECTOR = 'nav, footer, [role="navigation"], [role="contentinfo"]'
HIDDEN_STYLE = re.compile(
    r"display\s*:\s*none|visibility\s*:\s*hidden|opacity\s*:\s*0(?![.\d])|font-size\s*:\s*0(?![.\d])"
    r"|(?:left|top|text-indent)\s*:\s*-\d{3,}",
    re.I,
)


@dataclass
class CleanPage:
    text: str           # About or Home text: what is saved and what the model reads
    language: str
    identity_text: str  # all visible text, footer included: the organisation number usually sits there


def is_hidden(node) -> bool:
    attrs = node.attributes
    if node.tag in HIDDEN_TAGS or "hidden" in attrs or attrs.get("aria-hidden") == "true":
        return True
    return HIDDEN_STYLE.search(attrs.get("style") or "") is not None


def is_boilerplate(node) -> bool:
    return node.tag in ("nav", "footer") or node.attributes.get("role") in ("navigation", "contentinfo")


def drop_nodes(tree: LexborHTMLParser, selector: str, test) -> None:
    # children come after their parents, so walking backwards never touches a removed node
    for node in reversed(tree.css(selector)):
        if test(node):
            node.decompose()


def visible_text(tree: LexborHTMLParser) -> str:
    body = tree.body or tree.root
    return normalise_text(body.text(separator="\n", strip=True)) if body else ""


def main_text(tree: LexborHTMLParser) -> str:
    plain = visible_text(tree)
    extracted = trafilatura.extract(tree.html, favor_recall=True, include_comments=False)
    # trafilatura drops short About pages now and then; keep the plain text when it loses too much
    if extracted and len(extracted) >= len(plain) * 0.5:
        return normalise_text(extracted)
    return plain


def cut(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(None, 1)[0].rstrip()


def clean_html(html: str, headers=None, max_chars: int = 6000) -> CleanPage:
    tree = LexborHTMLParser(html)
    drop_nodes(tree, HIDDEN_SELECTOR, is_hidden)
    identity_text = cut(visible_text(tree), IDENTITY_TEXT_CHARS)
    drop_nodes(tree, BOILERPLATE_SELECTOR, is_boilerplate)
    text = cut(main_text(tree), max_chars)
    if not text:
        return CleanPage("", "unknown", identity_text)
    return CleanPage(text, detect_language(html, headers, text), identity_text)
