import urllib.error

from moonface.data.http import retrying


def test_returns_the_wrapped_result_on_success():
    wrapped = retrying(lambda url: f"ok:{url}")
    assert wrapped("http://x") == "ok:http://x"


def test_retries_on_transient_url_error_then_succeeds():
    calls = []

    def flaky(url):
        calls.append(url)
        if len(calls) < 3:
            raise urllib.error.URLError("boom")
        return "recovered"

    wrapped = retrying(flaky, attempts=4, sleep=lambda _: None)
    assert wrapped("http://x") == "recovered"
    assert len(calls) == 3


def test_reraises_after_exhausting_attempts():
    def always_fails(url):
        raise urllib.error.URLError("boom")

    wrapped = retrying(always_fails, attempts=2, sleep=lambda _: None)
    try:
        wrapped("http://x")
        assert False, "expected URLError"
    except urllib.error.URLError:
        pass


def test_http_error_is_not_retried():
    calls = []

    def bad_response(url):
        calls.append(url)
        raise urllib.error.HTTPError(url, 404, "not found", {}, None)

    wrapped = retrying(bad_response, attempts=4, sleep=lambda _: None)
    try:
        wrapped("http://x")
        assert False, "expected HTTPError"
    except urllib.error.HTTPError:
        pass
    assert len(calls) == 1  # no retry -- a served response, not a transport failure
