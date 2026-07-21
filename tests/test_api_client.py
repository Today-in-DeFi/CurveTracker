"""Tests for the shared HTTP client: timeouts, retries, and — most
importantly — that a failure is distinguishable from a genuine empty result.
"""

import pytest
import requests
import responses

import curve_tracker
from curve_tracker import (
    REQUEST_ATTEMPTS,
    REQUEST_TIMEOUT,
    BeefyAPI,
    ConvexAPI,
    CurveAPI,
    CurveTracker,
    JSONAPIClient,
    StakeDAOAPI,
)


@pytest.fixture(autouse=True)
def no_backoff_sleep(monkeypatch):
    """Keep retry tests fast; the backoff duration is asserted separately."""
    monkeypatch.setattr(curve_tracker.time, "sleep", lambda _: None)


class FakeAPI(JSONAPIClient):
    BASE_URL = "https://fake.test"
    LABEL = "Fake API"


class TestRetryBehaviour:
    @responses.activate
    def test_succeeds_without_retrying_on_first_success(self):
        responses.add(responses.GET, "https://fake.test/thing", json={"ok": True})
        client = FakeAPI()
        assert client._make_request("thing") == {"ok": True}
        assert len(responses.calls) == 1
        assert client.degraded is False

    @responses.activate
    def test_retries_then_succeeds(self):
        responses.add(responses.GET, "https://fake.test/thing", status=503)
        responses.add(responses.GET, "https://fake.test/thing", json={"ok": True})
        client = FakeAPI()
        assert client._make_request("thing") == {"ok": True}
        assert len(responses.calls) == 2
        assert client.degraded is False, "a recovered request is not a failure"

    @responses.activate
    def test_gives_up_after_configured_attempts(self):
        responses.add(responses.GET, "https://fake.test/thing", status=500)
        client = FakeAPI()
        assert client._make_request("thing") == {}
        assert len(responses.calls) == REQUEST_ATTEMPTS

    @responses.activate
    def test_backoff_grows_exponentially(self, monkeypatch):
        delays = []
        monkeypatch.setattr(curve_tracker.time, "sleep", delays.append)
        responses.add(responses.GET, "https://fake.test/thing", status=500)
        FakeAPI()._make_request("thing")
        assert delays == [2, 4]  # sleeps happen between attempts, not after the last


class TestFailureIsDistinguishableFromEmpty:
    """The bug this guards: {} on failure looked identical to a real empty
    response, so an outage was silently recorded as zeros."""

    @responses.activate
    def test_failure_is_recorded(self):
        responses.add(responses.GET, "https://fake.test/thing", status=500)
        client = FakeAPI()
        client._make_request("thing")
        assert client.degraded is True
        assert "thing" in client.failed_endpoints

    @responses.activate
    def test_genuinely_empty_response_is_not_marked_degraded(self):
        responses.add(responses.GET, "https://fake.test/thing", json={})
        client = FakeAPI()
        assert client._make_request("thing") == {}
        assert client.degraded is False, "an empty 200 is data, not a failure"

    @responses.activate
    def test_html_error_page_with_200_status_counts_as_failure(self):
        # Gateways return 200 + HTML; json() raises ValueError, which used to
        # escape uncaught rather than being handled as a failure.
        responses.add(
            responses.GET, "https://fake.test/thing", body="<html>502</html>", status=200
        )
        client = FakeAPI()
        assert client._make_request("thing") == {}
        assert client.degraded is True

    @responses.activate
    def test_connection_error_counts_as_failure(self):
        responses.add(
            responses.GET, "https://fake.test/thing", body=requests.ConnectionError("down")
        )
        client = FakeAPI()
        assert client._make_request("thing") == {}
        assert client.degraded is True


class TestTimeouts:
    @responses.activate
    def test_every_request_sets_a_timeout(self):
        """A missing timeout lets a hung upstream stall the whole cron run."""
        captured = {}

        def capture(request):
            captured["timeout"] = request.req_kwargs.get("timeout")
            return (200, {}, "{}")

        responses.add_callback(
            responses.GET, "https://fake.test/thing", callback=capture,
            content_type="application/json",
        )
        FakeAPI()._make_request("thing")
        assert captured["timeout"] == REQUEST_TIMEOUT


class TestAllClientsShareTheBehaviour:
    @pytest.mark.parametrize("cls", [CurveAPI, StakeDAOAPI, BeefyAPI, ConvexAPI])
    def test_client_inherits_retry_and_failure_tracking(self, cls):
        client = cls()
        assert isinstance(client, JSONAPIClient)
        assert client.failed_endpoints == []
        assert client.degraded is False

    @responses.activate
    def test_absolute_urls_are_supported(self):
        # Convex passes full URLs rather than BASE_URL-relative endpoints.
        responses.add(
            responses.GET,
            "https://curve.convexfinance.com/api/curve/pools",
            json={"pools": [{"address": "0xabc"}]},
        )
        assert ConvexAPI()._fetch_pools() == [{"address": "0xabc"}]


class TestDegradedSourcesReporting:
    def test_reports_nothing_on_a_clean_run(self):
        tracker = CurveTracker(enable_stakedao=True, enable_beefy=True)
        assert tracker.degraded_sources() == []

    def test_names_each_failed_source(self):
        tracker = CurveTracker(enable_stakedao=True, enable_beefy=True, enable_convex=True)
        tracker.api.failed_endpoints.append("getPools/all/ethereum")
        tracker.beefy_api.failed_endpoints.append("apy")
        assert sorted(tracker.degraded_sources()) == ["Beefy", "Curve"]

    def test_disabled_integrations_are_not_reported(self):
        # A disabled client is None, not a failure.
        tracker = CurveTracker(enable_stakedao=False, enable_beefy=False)
        tracker.api.failed_endpoints.append("getAllGauges")
        assert tracker.degraded_sources() == ["Curve"]
