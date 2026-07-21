"""Tests for the shared fail-loud RPC client and the chain fetchers.

These fetchers used to return '0x0' on any exception, which callers parsed
as integer zero. One dropped eth_call therefore removed a whole leg from a
pool's TVL while leaving the total non-zero -- so the sanity gate's
zero-drop rule passed it, degraded_sources stayed empty, and the run
reported clean success with a halved TVL.
"""

import pytest

from monad_onchain import MonadOnChainFetcher
from onchain_rpc import JSONRPCClient, RPCError
from plasma_onchain import PlasmaOnChainFetcher


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def word(value):
    return '0x' + format(value, '064x')


class TestClientFailsLoudly:
    def test_transport_failure_raises(self, monkeypatch):
        c = JSONRPCClient(['http://a'])
        monkeypatch.setattr(c.session, 'post',
                            lambda *a, **k: (_ for _ in ()).throw(OSError('down')))
        with pytest.raises(RPCError):
            c.call('0xpool', '0xdata')

    def test_error_payload_raises(self, monkeypatch):
        c = JSONRPCClient(['http://a'])
        monkeypatch.setattr(c.session, 'post',
                            lambda *a, **k: FakeResponse({'error': {'message': 'x'}}))
        with pytest.raises(RPCError):
            c.call('0xpool', '0xdata')

    def test_empty_result_raises_rather_than_zeroing(self, monkeypatch):
        """'0x' means reverted or no such method, not a balance of zero."""
        c = JSONRPCClient(['http://a'])
        monkeypatch.setattr(c.session, 'post',
                            lambda *a, **k: FakeResponse({'result': '0x'}))
        with pytest.raises(RPCError):
            c.call_uint('0xpool', '0xdata')

    def test_a_real_zero_is_still_returned(self, monkeypatch):
        """A contract genuinely reporting 0 must not be mistaken for failure."""
        c = JSONRPCClient(['http://a'])
        monkeypatch.setattr(c.session, 'post',
                            lambda *a, **k: FakeResponse({'result': word(0)}))
        assert c.call_uint('0xpool', '0xdata') == 0

    def test_failover_to_second_endpoint(self, monkeypatch):
        calls = []

        def post(url, **kwargs):
            calls.append(url)
            if len(calls) == 1:
                raise OSError('down')
            return FakeResponse({'result': word(42)})

        c = JSONRPCClient(['http://a', 'http://b'])
        monkeypatch.setattr(c.session, 'post', post)
        assert c.call_uint('0xpool', '0xdata') == 42
        assert len(calls) == 2


@pytest.fixture(params=[PlasmaOnChainFetcher, MonadOnChainFetcher])
def fetcher(request):
    return request.param(rpc_urls=['http://stub'])


TOKENS = [{'symbol': 'USDT', 'decimals': 6}, {'symbol': 'USDe', 'decimals': 18}]


class TestPartialReadsAreRefused:
    """The core regression: a TVL missing one leg is indistinguishable from
    a real TVL, so it must never be returned."""

    def test_second_leg_failing_refuses_the_whole_pool(self, fetcher, monkeypatch):
        calls = []

        def post(url, json=None, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                return FakeResponse({'result': word(772_590_000_000)})
            raise OSError('rate limited')

        monkeypatch.setattr(fetcher.client.session, 'post', post)

        with pytest.raises(RPCError) as exc:
            fetcher.get_pool_data('0xpool', TOKENS)
        assert 'USDe' in str(exc.value)

    def test_first_leg_failing_refuses_the_whole_pool(self, fetcher, monkeypatch):
        monkeypatch.setattr(fetcher.client.session, 'post',
                            lambda *a, **k: (_ for _ in ()).throw(OSError('down')))
        with pytest.raises(RPCError):
            fetcher.get_pool_data('0xpool', TOKENS)

    def test_no_partial_tvl_is_ever_returned(self, fetcher, monkeypatch):
        """Previously this returned tvl=772590.0 -- plausible, and wrong."""
        calls = []

        def post(url, json=None, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                return FakeResponse({'result': word(772_590_000_000)})
            return FakeResponse({'result': '0x'})

        monkeypatch.setattr(fetcher.client.session, 'post', post)
        with pytest.raises(RPCError):
            fetcher.get_pool_data('0xpool', TOKENS)


class TestHealthyReads:
    def test_all_legs_readable_returns_tvl(self, monkeypatch):
        f = PlasmaOnChainFetcher(rpc_urls=['http://stub'])
        amounts = iter([word(1_000_000), word(2 * 10 ** 18)])
        monkeypatch.setattr(f.client.session, 'post',
                            lambda *a, **k: FakeResponse({'result': next(amounts)}))

        data = f.get_pool_data('0xpool', TOKENS)
        assert data['balances'] == [1.0, 2.0]
        assert data['tvl'] == 3.0

    def test_genuine_zero_balance_is_reported(self, monkeypatch):
        """An empty pool is real data and must survive."""
        f = PlasmaOnChainFetcher(rpc_urls=['http://stub'])
        monkeypatch.setattr(f.client.session, 'post',
                            lambda *a, **k: FakeResponse({'result': word(0)}))

        data = f.get_pool_data('0xpool', TOKENS)
        assert data['tvl'] == 0.0
