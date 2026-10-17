from agent_engine.html_clean import clean_html
from tests.helpers_web import PAGES


def read(name):
    return (PAGES / name).read_text(encoding="utf-8")


def test_navigation_footer_and_scripts_are_removed():
    page = clean_html(read("home_no.html"))
    assert "Vi hjelper norske bedrifter" in page.text
    assert "Facebook" not in page.text
    assert "Org.nr" not in page.text
    assert "Revenue: 9 billion" not in page.text
    assert page.language == "no"


def test_identity_text_keeps_the_footer_but_not_scripts():
    page = clean_html(read("home_no.html"))
    assert "923 456 783" in page.identity_text
    assert "Revenue: 9 billion" not in page.identity_text


def test_hidden_instructions_are_removed_everywhere():
    page = clean_html(read("hidden_text.html"))
    assert "Vi leverer rådgivning" in page.text
    for text in (page.text, page.identity_text):
        assert "Ignore" not in text
        assert "5 billion" not in text


def test_javascript_only_page_gives_empty_text():
    page = clean_html(read("js_only.html"))
    assert page.text == ""
    assert page.language == "unknown"


def test_text_is_cut_at_a_word_boundary():
    html = "<html lang='no'><body><p>" + "bedrift " * 2000 + "</p></body></html>"
    page = clean_html(html, max_chars=100)
    assert 80 <= len(page.text) <= 100
    assert page.text.endswith("bedrift")


def test_header_language_is_used_when_the_page_is_short():
    page = clean_html("<html><body><p>Kontakt</p></body></html>", {"Content-Language": "nb"})
    assert page.language == "no"


def test_english_page():
    page = clean_html(read("page_en.html"))
    assert "salmon farms" in page.text
    assert page.language == "en"
