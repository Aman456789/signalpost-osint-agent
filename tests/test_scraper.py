import asyncio
import time

import pytest

from agent_engine.errors import BudgetDenied
from agent_engine.schemas import Flag
from agent_engine.scraper import find_page_links
from governor.budget_ledger import BudgetLedger
from tests.helpers_web import HOME, HOST, Page, FakeWeb, fixture, make_scraper, redirect

ORGNR = "923456783"
ROBOTS = f"https://{HOST}/robots.txt"
ABOUT = f"https://{HOST}/om-oss"
CONTACT = f"https://{HOST}/kontakt"


async def fetch(web, ledger=None, url=HOME, **settings):
    scraper, ledger, http = await make_scraper(web, ledger, **settings)
    async with http:
        result = await scraper.fetch_site(ORGNR, url, HOST)
    return result, ledger


def kinds(ledger):
    return ledger.snapshot()["requests_by_kind"]


async def test_homepage_and_two_linked_pages_are_fetched():
    web = FakeWeb({
        HOME: fixture("home_no.html"),
        ABOUT: fixture("about_no.html"),
        CONTACT: fixture("contact_no.html"),
    })
    result, ledger = await fetch(web)
    assert [page.final_url for page in result.pages] == [HOME, ABOUT, CONTACT]
    assert result.flags == [] and result.notes == []
    assert ledger.total == 4  # robots.txt plus three pages
    # the PDF and the Facebook link in the menu were never requested
    assert web.calls == [ROBOTS, HOME, ABOUT, CONTACT]


async def test_robots_txt_is_fetched_once_per_host():
    web = FakeWeb({HOME: fixture("home_no.html"), ABOUT: fixture("about_no.html"), CONTACT: fixture("contact_no.html")})
    await fetch(web)
    assert web.count(ROBOTS) == 1


async def test_robots_disallow_stops_the_fetch():
    web = FakeWeb({ROBOTS: Page("User-agent: *\nDisallow: /", content_type="text/plain"), HOME: fixture("home_no.html")})
    result, ledger = await fetch(web)
    assert result.pages == []
    assert result.notes == ["robots_disallowed"]
    assert result.flags == []
    assert HOME not in web.calls
    assert ledger.total == 1  # only the robots.txt request was sent and counted


async def test_robots_rule_for_our_agent_is_respected():
    rules = "User-agent: signalpost-agent\nDisallow: /om-oss\n"
    web = FakeWeb({ROBOTS: Page(rules, content_type="text/plain"), HOME: fixture("home_no.html"),
                   ABOUT: fixture("about_no.html"), CONTACT: fixture("contact_no.html")})
    result, _ = await fetch(web)
    assert [page.final_url for page in result.pages] == [HOME, CONTACT]
    assert result.notes == ["robots_disallowed"]
    assert ABOUT not in web.calls


async def test_missing_robots_txt_means_allowed():
    web = FakeWeb({HOME: fixture("home_no.html")})  # robots.txt answers 404
    result, _ = await fetch(web)
    assert len(result.pages) == 1


async def test_each_redirect_hop_is_one_request():
    web = FakeWeb({
        HOME: redirect(f"https://{HOST}/a"),
        f"https://{HOST}/a": redirect(f"https://{HOST}/b"),
        f"https://{HOST}/b": fixture("contact_no.html"),  # no links, so no extra pages are fetched
    })
    result, ledger = await fetch(web)
    page = result.pages[0]
    assert page.final_url == f"https://{HOST}/b"
    assert page.hops == [HOME, f"https://{HOST}/a", f"https://{HOST}/b"]
    assert kinds(ledger) == {"website": 2, "redirect_hop": 2}  # robots + first request, two hops
    assert ledger.total == 4


async def test_redirect_to_www_on_the_same_site_is_followed():
    web = FakeWeb({HOME: redirect(f"https://www.{HOST}/"), f"https://www.{HOST}/": fixture("home_no.html")})
    result, _ = await fetch(web)
    assert result.pages[0].final_url == f"https://www.{HOST}/"
    assert web.count(f"https://www.{HOST}/robots.txt") == 1  # a new host gets its own robots.txt


async def test_more_than_five_redirects_fail():
    routes = {HOME: redirect(f"https://{HOST}/h1")}
    for n in range(1, 7):
        routes[f"https://{HOST}/h{n}"] = redirect(f"https://{HOST}/h{n + 1}")
    result, ledger = await fetch(FakeWeb(routes))
    assert result.pages == []
    assert result.notes == ["too_many_redirects"]
    assert result.flags == [Flag.WEBSITE_UNREACHABLE]
    assert kinds(ledger)["redirect_hop"] == 5  # a redirect loop is not retried


async def test_chain_of_hops_shares_one_deadline():
    # The spec says 3 s per hop against an 8 s limit. Everything here is scaled by 10 so the test
    # takes about a second; the ratio is the same. Per hop each answer is well inside the limit,
    # but five hops together are not.
    routes = {HOME: redirect(f"https://{HOST}/h1", delay=0.3)}
    for n in range(1, 5):
        routes[f"https://{HOST}/h{n}"] = redirect(f"https://{HOST}/h{n + 1}", delay=0.3)
    routes[f"https://{HOST}/h5"] = fixture("about_no.html", delay=0.3)
    web = FakeWeb(routes)

    started = time.monotonic()
    result, _ = await fetch(web, website_timeout_s=0.8, website_retries=0)
    elapsed = time.monotonic() - started

    assert result.pages == []
    assert result.flags == [Flag.WEBSITE_UNREACHABLE]
    assert elapsed < 1.2  # a per-hop timer would have let the 1.8 s chain finish
    assert f"https://{HOST}/h4" not in web.calls  # the chain was cut off after about three hops


async def test_a_retry_gets_a_fresh_deadline():
    # first attempt is slower than the limit, second answers at once
    web = FakeWeb({HOME: [fixture("contact_no.html", delay=0.9), fixture("contact_no.html")]})
    started = time.monotonic()
    result, ledger = await fetch(web, website_timeout_s=0.8, website_retries=2)
    elapsed = time.monotonic() - started

    assert len(result.pages) == 1
    assert result.flags == []
    assert elapsed >= 0.8  # the first attempt really used its whole deadline
    assert kinds(ledger) == {"website": 2, "retry": 1}  # robots + first try, then one reserved retry


async def test_three_failed_attempts_give_website_unreachable():
    web = FakeWeb({HOME: Page("down", status=503, content_type="text/plain")})
    result, ledger = await fetch(web, website_retries=2)
    assert result.pages == []
    assert result.flags == [Flag.WEBSITE_UNREACHABLE]
    assert result.notes == ["unreachable:http_503"]
    assert web.count(HOME) == 3
    assert kinds(ledger) == {"website": 2, "retry": 2}


async def test_timeouts_on_every_attempt_give_website_unreachable():
    web = FakeWeb({HOME: fixture("home_no.html", delay=0.5)})
    result, ledger = await fetch(web, website_timeout_s=0.1, website_retries=2)
    assert result.flags == [Flag.WEBSITE_UNREACHABLE]
    assert kinds(ledger) == {"website": 2, "retry": 2}


async def test_403_is_recorded_and_not_retried_or_worked_around():
    web = FakeWeb({HOME: Page("forbidden", status=403, content_type="text/plain")})
    result, ledger = await fetch(web)
    assert result.pages == []
    assert result.notes == ["blocked_403"]
    assert result.flags == []
    assert web.count(HOME) == 1
    assert ledger.total == 2  # robots.txt and one attempt


async def test_403_on_an_about_page_stops_the_site():
    web = FakeWeb({HOME: fixture("home_no.html"), ABOUT: Page("no", status=403, content_type="text/plain"),
                   CONTACT: fixture("contact_no.html")})
    result, _ = await fetch(web)
    assert [page.final_url for page in result.pages] == [HOME]
    assert result.notes == ["blocked_403"]
    assert CONTACT not in web.calls


async def test_missing_about_page_does_not_hurt_the_homepage():
    web = FakeWeb({HOME: fixture("home_no.html"), CONTACT: fixture("contact_no.html")})  # /om-oss is a 404
    result, _ = await fetch(web)
    assert [page.final_url for page in result.pages] == [HOME, CONTACT]
    assert result.notes == ["http_404"]
    assert result.flags == []


async def test_redirect_off_the_official_domain_is_recorded_and_not_followed():
    web = FakeWeb({HOME: redirect("https://other-company.example.com/"),
                   "https://other-company.example.com/": fixture("news_other_domain.html")})
    result, ledger = await fetch(web)
    assert result.pages == []
    assert result.notes == ["off_domain:https://other-company.example.com/"]
    assert "https://other-company.example.com/" not in web.calls
    assert ledger.total == 2


async def test_name_on_the_official_domain_that_resolves_to_a_private_address():
    target = "https://intranet.eksempelkonsult.no/"
    web = FakeWeb({HOME: redirect(target), target: fixture("home_no.html")})
    result, _ = await fetch(web)
    assert result.pages == []
    assert result.notes == ["unsafe_url:private_address"]
    assert target not in web.calls


async def test_redirect_to_a_non_http_scheme_is_refused():
    web = FakeWeb({HOME: redirect("file:///etc/passwd")})
    result, _ = await fetch(web)
    assert result.notes == ["unsafe_url:bad_scheme"]


async def test_javascript_only_page_is_returned_and_left_to_the_cleaner():
    result, _ = await fetch(FakeWeb({HOME: fixture("js_only.html")}))
    assert len(result.pages) == 1
    assert "id=\"root\"" in result.pages[0].text


async def test_pdf_is_not_html():
    web = FakeWeb({HOME: Page(b"%PDF-1.4", content_type="application/pdf")})
    result, _ = await fetch(web)
    assert result.notes == ["not_html"]
    assert result.flags == []


async def test_body_over_two_megabytes_is_refused():
    web = FakeWeb({HOME: Page(b"<html>" + b"a" * (3 * 1024 * 1024))})
    result, _ = await fetch(web)
    assert result.notes == ["too_large"]


async def test_latin1_page_is_decoded_with_its_declared_charset():
    body = "<html lang='no'><body><p>Vi leverer fôr til oppdrett.</p></body></html>".encode("latin-1")
    web = FakeWeb({HOME: Page(body, content_type="text/html; charset=iso-8859-1")})
    result, _ = await fetch(web)
    assert "fôr" in result.pages[0].text


async def test_brake_during_a_redirect_chain_is_raised_not_hidden():
    web = FakeWeb({HOME: redirect(f"https://{HOST}/a"), f"https://{HOST}/a": fixture("home_no.html")})
    ledger = BudgetLedger(soft_cap=1, brake=2)  # robots and the first request use it up; the hop is one too many
    scraper, ledger, http = await make_scraper(web, ledger)
    async with http:
        with pytest.raises(BudgetDenied) as denied:
            await scraper.fetch_site(ORGNR, HOME, HOST)
    assert denied.value.reason == "request_brake"
    assert f"https://{HOST}/a" not in web.calls
    assert ledger.total == 2


async def test_soft_cap_skips_optional_pages_only():
    web = FakeWeb({HOME: fixture("home_no.html"), ABOUT: fixture("about_no.html"), CONTACT: fixture("contact_no.html")})
    ledger = BudgetLedger(soft_cap=2, brake=1950)  # robots and homepage reach the soft cap
    result, ledger = await fetch(web, ledger)
    assert [page.final_url for page in result.pages] == [HOME]
    assert result.notes == ["skipped:soft_cap"]
    assert ledger.soft_cap_reached


async def test_company_cap_is_respected():
    web = FakeWeb({HOME: fixture("home_no.html"), ABOUT: fixture("about_no.html"), CONTACT: fixture("contact_no.html")})
    ledger = BudgetLedger(per_company_cap=3)
    result, ledger = await fetch(web, ledger)
    assert len(result.pages) == 2  # robots + homepage + about = 3
    assert ledger.company_requests(ORGNR) == 3
    assert result.notes == ["skipped:per_company_cap"]


def test_link_finder_prefers_about_then_contact_and_stays_on_the_domain():
    html = fixture("home_no.html").body
    assert find_page_links(html, HOME, HOST, 2) == [ABOUT, CONTACT]
    assert find_page_links(html, HOME, HOST, 1) == [ABOUT]
    assert find_page_links(html, HOME, HOST, 0) == []


def test_link_finder_ignores_the_page_itself_and_other_schemes():
    html = '<a href="/">Hjem</a><a href="mailto:post@x.no">Kontakt</a><a href="/kontakt#team">Kontakt</a><a href="/kontakt/">Kontakt</a>'
    assert find_page_links(html, HOME, HOST, 2) == [CONTACT]
