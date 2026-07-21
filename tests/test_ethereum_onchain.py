"""Tests for the gauge reward on-chain reads.

The point of this module is that a stream's expiry cannot be inferred from
its APY. These tests pin the decoding and, above all, that failures raise
rather than returning a zero that would read as "expired in 1970".
"""

import pytest

from ethereum_onchain import (
    REWARD_DATA_SELECTOR,
    EthereumRPC,
    RPCError,
    _split_words,
    _to_iso,
    is_stream_active,
    seconds_until_expiry,
)

# Real reward_data() return for BOLD on gauge 0x07a0...5e9, read 2026-07-21.
# Word 0 (token) is zero on this gauge -- decoding must not depend on it.
BOLD_RAW = (
    '0x'
    '0000000000000000000000000000000000000000000000000000000000000000'  # token
    '000000000000000000000000ba3ce7d0bf2d4c8bc44a2eb8f5e6e2d61f0aa1f4'  # distributor
    '000000000000000000000000000000000000000000000000000000006a5f8383'  # period_finish
    '00000000000000000000000000000000000000000000000000316d3c11f7d0cb'  # rate
    '000000000000000000000000000000000000000000000000000000006a5cdc8b'  # last_update
    '00000000000000000000000000000000000000000000000000d0348d9ff2c942'  # integral
)


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class TestDecoding:
    def test_period_finish_is_read_positionally(self):
        words = _split_words(BOLD_RAW)
        assert len(words) == 6
        assert words[2] == 0x6a5f8383

    def test_zero_token_word_does_not_break_decoding(self):
        """This gauge leaves word 0 unset; it must not be used to validate."""
        assert _split_words(BOLD_RAW)[0] == 0

    def test_iso_formatting(self):
        assert _to_iso(1784765123) == '2026-07-23T00:05:23Z'

    def test_unset_timestamp_is_none_not_epoch(self):
        assert _to_iso(0) is None


class TestActivity:
    def test_future_expiry_is_active(self):
        assert is_stream_active(2_000_000_000, now=1_784_000_000)

    def test_past_expiry_is_inactive(self):
        assert not is_stream_active(1_747_873_307, now=1_784_000_000)

    def test_unset_expiry_is_inactive(self):
        assert not is_stream_active(0, now=1_784_000_000)

    def test_a_funded_stream_paying_zero_still_reads_active(self):
        """The whole point of period_finish over the apy > 0 proxy."""
        assert is_stream_active(2_000_000_000, now=1_784_000_000)

    def test_seconds_until_expiry_is_negative_once_lapsed(self):
        assert seconds_until_expiry(1_000, now=2_000) == -1_000

    def test_seconds_until_expiry_unset_is_none(self):
        assert seconds_until_expiry(0, now=2_000) is None


class TestFailsLoudly:
    """A zero sentinel here would read as a real expiry. It must raise."""

    def test_all_endpoints_failing_raises(self, monkeypatch):
        rpc = EthereumRPC(rpc_urls=['http://a', 'http://b'])
        monkeypatch.setattr(rpc.session, 'post',
                            lambda *a, **k: (_ for _ in ()).throw(OSError('down')))
        with pytest.raises(RPCError):
            rpc.get_reward_data('0xgauge', '0xtoken')

    def test_rpc_error_payload_raises(self, monkeypatch):
        rpc = EthereumRPC(rpc_urls=['http://a'])
        monkeypatch.setattr(rpc.session, 'post',
                            lambda *a, **k: FakeResponse({'error': {'message': 'nope'}}))
        with pytest.raises(RPCError):
            rpc.get_reward_data('0xgauge', '0xtoken')

    def test_empty_result_raises_rather_than_zeroing(self, monkeypatch):
        rpc = EthereumRPC(rpc_urls=['http://a'])
        monkeypatch.setattr(rpc.session, 'post',
                            lambda *a, **k: FakeResponse({'result': '0x'}))
        with pytest.raises(RPCError):
            rpc.get_reward_data('0xgauge', '0xtoken')

    def test_short_return_raises(self, monkeypatch):
        """A gauge with a different ABI must error, not misread word 2."""
        rpc = EthereumRPC(rpc_urls=['http://a'])
        monkeypatch.setattr(rpc.session, 'post',
                            lambda *a, **k: FakeResponse({'result': '0x' + '00' * 32}))
        with pytest.raises(RPCError):
            rpc.get_reward_data('0xgauge', '0xtoken')

    def test_missing_addresses_raise(self):
        with pytest.raises(RPCError):
            EthereumRPC(rpc_urls=['http://a']).get_reward_data('', '0xtoken')


class TestFailover:
    def test_second_endpoint_is_tried_when_first_fails(self, monkeypatch):
        calls = []

        def fake_post(url, **kwargs):
            calls.append(url)
            if len(calls) == 1:
                raise OSError('first is down')
            return FakeResponse({'result': BOLD_RAW})

        rpc = EthereumRPC(rpc_urls=['http://a', 'http://b'])
        monkeypatch.setattr(rpc.session, 'post', fake_post)
        data = rpc.get_reward_data('0xgauge', '0xtoken')

        assert len(calls) == 2
        assert data['period_finish'] == 0x6a5f8383


class TestRequestShape:
    def test_token_is_abi_padded_into_the_call(self, monkeypatch):
        seen = {}

        def fake_post(url, json=None, **kwargs):
            seen['data'] = json['params'][0]['data']
            return FakeResponse({'result': BOLD_RAW})

        rpc = EthereumRPC(rpc_urls=['http://a'])
        monkeypatch.setattr(rpc.session, 'post', fake_post)
        rpc.get_reward_data('0xgauge', '0x6440f144b7e50D6a8439336510312d2F54beB01D')

        assert seen['data'].startswith(REWARD_DATA_SELECTOR)
        assert seen['data'].endswith('6440f144b7e50d6a8439336510312d2f54beb01d')
        assert len(seen['data']) == len(REWARD_DATA_SELECTOR) + 64
