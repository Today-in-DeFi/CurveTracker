"""Tests for pool validation.

validate_pool used to return True whenever the Curve API errored, meaning an
invalid pool was accepted precisely when it could not be checked. It now
fails closed; --no-validate remains the deliberate override.
"""

import json

import pytest
import requests
import responses

from pool_manager import PoolManager

POOLS_URL = "https://api.curve.finance/v1/getPools/all/ethereum"
KNOWN_ADDRESS = "0xc522a6606bba746d7960404f22a3db936b6f4f50"


def _api_payload(*addresses):
    return {
        "data": {
            "poolData": [
                {"address": a, "name": f"pool-{i}"} for i, a in enumerate(addresses)
            ]
        }
    }


@pytest.fixture
def manager(tmp_path):
    """A PoolManager backed by a throwaway config, never the real pools.json."""
    config = tmp_path / "pools.json"
    config.write_text(json.dumps({"pools": []}))
    return PoolManager(str(config))


class TestConfirmedPools:
    @responses.activate
    def test_known_address_validates(self, manager):
        responses.add(responses.GET, POOLS_URL, json=_api_payload(KNOWN_ADDRESS))
        assert manager.validate_pool("ethereum", KNOWN_ADDRESS) is True

    @responses.activate
    def test_address_match_is_case_insensitive(self, manager):
        responses.add(responses.GET, POOLS_URL, json=_api_payload(KNOWN_ADDRESS))
        assert manager.validate_pool("ethereum", KNOWN_ADDRESS.upper()) is True

    @responses.activate
    def test_unknown_address_does_not_validate(self, manager):
        responses.add(responses.GET, POOLS_URL, json=_api_payload(KNOWN_ADDRESS))
        assert manager.validate_pool("ethereum", "0xdeadbeef") is False


class TestFailsClosed:
    """The bug: an unreachable API used to mean 'yes'."""

    @responses.activate
    def test_server_error_does_not_validate(self, manager):
        responses.add(responses.GET, POOLS_URL, status=500)
        assert manager.validate_pool("ethereum", KNOWN_ADDRESS) is False

    @responses.activate
    def test_connection_error_does_not_validate(self, manager):
        responses.add(
            responses.GET, POOLS_URL, body=requests.ConnectionError("network down")
        )
        assert manager.validate_pool("ethereum", KNOWN_ADDRESS) is False

    @responses.activate
    def test_malformed_json_does_not_validate(self, manager):
        responses.add(responses.GET, POOLS_URL, body="<html>502</html>", status=200)
        assert manager.validate_pool("ethereum", KNOWN_ADDRESS) is False

    @responses.activate
    def test_empty_payload_does_not_validate(self, manager):
        responses.add(responses.GET, POOLS_URL, json={})
        assert manager.validate_pool("ethereum", KNOWN_ADDRESS) is False

    @responses.activate
    def test_timeout_does_not_validate(self, manager):
        responses.add(responses.GET, POOLS_URL, body=requests.Timeout("slow"))
        assert manager.validate_pool("ethereum", KNOWN_ADDRESS) is False
