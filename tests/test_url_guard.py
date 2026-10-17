import pytest

from agent_engine.url_guard import UnsafeUrl, check_url, is_official_host


async def public(host):
    return ["93.184.216.34"]


async def private(host):
    return ["10.1.2.3"]


async def mixed(host):
    return ["93.184.216.34", "192.168.0.10"]


async def test_public_https_host_is_allowed():
    assert await check_url("https://Example.no/om-oss", public) == "example.no"


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/",
    "http://[::1]/",
    "http://10.0.0.1/",
    "http://172.16.5.4/",
    "http://192.168.1.1/",
    "http://169.254.169.254/latest/meta-data/",  # cloud metadata, link-local
    "http://100.64.0.1/",                        # carrier-grade NAT
    "http://[::ffff:127.0.0.1]/",                # IPv4 loopback written as IPv6
    "http://0.0.0.0/",
])
async def test_private_ip_literals_are_rejected(url):
    with pytest.raises(UnsafeUrl) as error:
        await check_url(url, public)
    assert error.value.reason == "private_address"


async def test_name_that_resolves_to_a_private_address_is_rejected():
    with pytest.raises(UnsafeUrl) as error:
        await check_url("https://intranet.example.no/", private)
    assert error.value.reason == "private_address"


async def test_one_private_answer_among_public_ones_is_enough_to_reject():
    with pytest.raises(UnsafeUrl):
        await check_url("https://example.no/", mixed)


async def test_redirect_target_is_checked_like_any_other_url():
    # a redirect from a public page to localhost is just another URL for the guard
    assert await check_url("https://example.no/", public) == "example.no"
    with pytest.raises(UnsafeUrl):
        await check_url("http://localhost/admin", lambda host: private(host))


@pytest.mark.parametrize("url, reason", [
    ("ftp://example.no/file", "bad_scheme"),
    ("file:///etc/passwd", "bad_scheme"),
    ("javascript:alert(1)", "bad_scheme"),
    ("https://user:secret@example.no/", "userinfo"),
    ("https://user@example.no/", "userinfo"),
    ("https://example.no:8080/", "bad_port"),
    ("http://example.no:22/", "bad_port"),
    ("https://example.no:99999/", "bad_port"),
    ("https:///path", "no_host"),
])
async def test_policy_violations(url, reason):
    with pytest.raises(UnsafeUrl) as error:
        await check_url(url, public)
    assert error.value.reason == reason


async def test_standard_ports_are_allowed():
    await check_url("http://example.no:80/", public)
    await check_url("https://example.no:443/", public)


async def test_dns_failure_is_not_hidden_as_a_policy_error():
    async def broken(host):
        raise OSError("name not known")

    with pytest.raises(OSError):
        await check_url("https://example.no/", broken)


def test_official_host_accepts_subdomains_but_not_look_alikes():
    assert is_official_host("www.example.no", "example.no")
    assert is_official_host("shop.example.no", "example.no")
    assert is_official_host("example.no.", "www.example.no")
    assert not is_official_host("evilexample.no", "example.no")
    assert not is_official_host("example.no.evil.com", "example.no")
    assert not is_official_host("example.com", "example.no")
    assert not is_official_host(None, "example.no")
    assert not is_official_host("example.no", None)
