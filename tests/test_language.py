from agent_engine.language import detect_language, extract_html_lang, guess_language
from tests.helpers_web import PAGES

NORWEGIAN = "Vi leverer fôr til lakseoppdrett over hele Norge."
ENGLISH = "We deliver feed to salmon farms across Norway."


def read(name):
    return (PAGES / name).read_text(encoding="utf-8")


def test_norwegian_page_tag():
    assert extract_html_lang(read("home_no.html")) == "no"


def test_english_page_tag():
    assert extract_html_lang(read("page_en.html")) == "en"


def test_bokmaal_and_nynorsk_count_as_norwegian():
    assert extract_html_lang('<html lang="nb-NO"></html>') == "no"
    assert extract_html_lang('<html lang="nn"></html>') == "no"


def test_missing_tag_is_unknown():
    assert extract_html_lang(read("js_only.html")) == "unknown"


def test_other_tags_are_read_in_order():
    meta = '<html><head><meta http-equiv="Content-Language" content="en-GB"></head></html>'
    assert extract_html_lang(meta) == "en"
    og = '<html><head><meta property="og:locale" content="nb_NO"></head></html>'
    assert extract_html_lang(og) == "no"
    assert extract_html_lang("<html></html>", {"Content-Language": "nb"}) == "no"


def test_other_language_is_unknown():
    assert extract_html_lang('<html lang="de"></html>') == "unknown"


def test_guess_from_text():
    assert guess_language(NORWEGIAN) == "no"
    assert guess_language(ENGLISH) == "en"


def test_short_or_unclear_text_is_unknown():
    assert guess_language("Eksempel AS") == "unknown"
    assert guess_language("") == "unknown"
    assert guess_language("12 land") == "unknown"


def test_a_wrong_tag_loses_to_clear_text():
    # lang="en" is a common default on Norwegian sites
    html = f'<html lang="en"><body><p>{NORWEGIAN}</p></body></html>'
    assert extract_html_lang(html) == "en"
    assert detect_language(html, {}, NORWEGIAN) == "no"


def test_tag_is_used_when_text_is_too_short_to_judge():
    html = '<html lang="no"><body><p>Kontakt</p></body></html>'
    assert detect_language(html, {}, "Kontakt") == "no"
