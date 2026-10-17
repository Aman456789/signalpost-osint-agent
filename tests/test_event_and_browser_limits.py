import asyncio

from agent_engine.schemas import MAX_EVENT_MESSAGE, truncate_message
from agent_engine.scraper import PLAYWRIGHT_MAX_BYTES, install_browser_size_guard, oversized
from api.routes_stream import public_event


def test_short_messages_are_unchanged():
    assert truncate_message("Job started") == "Job started"
    assert truncate_message("x" * MAX_EVENT_MESSAGE) == "x" * MAX_EVENT_MESSAGE


def test_long_messages_are_cut_to_300_characters_with_ellipsis():
    cut = truncate_message("y" * 1000)
    assert len(cut) == MAX_EVENT_MESSAGE and cut.endswith("...")


def test_public_event_truncates_the_message():
    event = {"seq": 1, "time": "2026-01-01T00:00:00+00:00", "job_id": "j", "type": "error",
             "data": {"error": "z" * 900}}
    assert len(public_event(event)["message"]) == MAX_EVENT_MESSAGE


def test_oversized_checks_declared_length_and_body():
    limit = PLAYWRIGHT_MAX_BYTES
    assert oversized({"Content-Length": str(limit + 1)})
    assert not oversized({"content-length": str(limit)})
    assert oversized({}, b"a" * (limit + 1))
    assert not oversized({}, b"a" * 10)


class _Req:
    def __init__(self, headers=None, body=None):
        self.headers, self.post_data_buffer = headers or {}, body


class _Resp:
    def __init__(self, headers, body):
        self.headers, self._body = headers, body

    async def body(self):
        return self._body


class _Route:
    def __init__(self, request, response):
        self.request, self._response = request, response
        self.aborted = self.fulfilled = None

    async def fetch(self):
        return self._response

    async def abort(self, code):
        self.aborted = code

    async def fulfill(self, response):
        self.fulfilled = response


class _Page:
    async def route(self, pattern, handler):
        self.handler = handler


def _run(route):
    async def go():
        page = _Page()
        await install_browser_size_guard(page)
        await page.handler(route)

    asyncio.run(go())


def test_guard_aborts_an_oversized_response():
    route = _Route(_Req(), _Resp({"content-length": str(PLAYWRIGHT_MAX_BYTES + 1)}, b""))
    _run(route)
    assert route.aborted == "blockedbyclient" and route.fulfilled is None


def test_guard_aborts_an_oversized_request():
    route = _Route(_Req({"content-length": str(PLAYWRIGHT_MAX_BYTES + 1)}), _Resp({}, b""))
    _run(route)
    assert route.aborted == "blockedbyclient"


def test_guard_lets_a_small_response_through():
    response = _Resp({"content-length": "10"}, b"0123456789")
    route = _Route(_Req(), response)
    _run(route)
    assert route.aborted is None and route.fulfilled is response
