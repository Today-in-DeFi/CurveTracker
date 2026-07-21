"""Shared JSON-RPC client for on-chain reads.

The contract this module exists to enforce: **a failed read raises**. It never
returns a sentinel.

The chain fetchers originally returned '0x0' on any exception, which callers
then parsed as an integer zero. One dropped eth_call therefore turned into a
balance of zero, and a pool's TVL silently came back missing one leg -- not
zero, so nothing downstream rejected it, and the sanity gate's zero-drop rule
passed it through. That is the plausible-looking-wrong-value failure this repo
keeps hitting, and a sentinel return is how it gets in.

Callers are expected to let RPCError propagate, or catch it and record the
source as degraded. They must never substitute a placeholder for a value they
could not read.
"""

from typing import List, Optional, Sequence

import requests

DEFAULT_TIMEOUT = 15


class RPCError(RuntimeError):
    """An on-chain read did not complete. Never carries a substitute value."""


class JSONRPCClient:
    """Minimal eth_call client that fails loudly and can fail over."""

    def __init__(self, rpc_urls: Sequence[str], timeout: int = DEFAULT_TIMEOUT,
                 label: str = "RPC"):
        if not rpc_urls:
            raise ValueError("at least one RPC URL is required")
        self.rpc_urls = list(rpc_urls)
        self.timeout = timeout
        self.label = label
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})

    def call(self, to: str, data: str) -> str:
        """eth_call returning raw hex. Raises RPCError if no endpoint answers."""
        payload = {
            'jsonrpc': '2.0',
            'method': 'eth_call',
            'params': [{'to': to, 'data': data}, 'latest'],
            'id': 1,
        }

        errors = []
        for url in self.rpc_urls:
            try:
                response = self.session.post(url, json=payload, timeout=self.timeout)
                response.raise_for_status()
                body = response.json()
            except Exception as e:
                errors.append(f"{url}: {e}")
                continue

            if 'error' in body:
                errors.append(f"{url}: {body['error']}")
                continue

            result = body.get('result')
            if not result or result == '0x':
                # An empty return means the call reverted or the method does
                # not exist -- not a contract reporting zero.
                errors.append(f"{url}: empty result")
                continue

            return result

        raise RPCError(f"{self.label} eth_call to {to} failed on all endpoints: "
                       f"{'; '.join(errors)}")

    def call_uint(self, to: str, data: str) -> int:
        """eth_call decoded as a single uint256."""
        raw = self.call(to, data)
        try:
            return int(raw, 16)
        except ValueError as e:
            raise RPCError(f"{self.label} could not decode {raw!r} as uint: {e}")

    def call_address(self, to: str, data: str) -> str:
        """eth_call decoded as a single address."""
        raw = self.call(to, data)
        body = raw[2:] if raw.startswith('0x') else raw
        if len(body) < 40:
            raise RPCError(f"{self.label} returned {raw!r}, too short for an address")
        return '0x' + body[-40:]

    def call_words(self, to: str, data: str) -> List[int]:
        """eth_call split into 32-byte words as ints."""
        raw = self.call(to, data)
        body = raw[2:] if raw.startswith('0x') else raw
        return [int(body[i:i + 64], 16) for i in range(0, len(body) - 63, 64)]
