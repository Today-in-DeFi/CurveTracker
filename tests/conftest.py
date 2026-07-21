"""Shared test fixtures.

Tests must never touch the network or the real `data/` directory. The
`exporter` fixture writes to a pytest tmp_path, and no test constructs a
client that performs a live request.
"""

import os
import sys

import pytest

# The project has no package layout; modules are imported from the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from curve_tracker import PoolData  # noqa: E402
from json_exporter import CurveDataExporter  # noqa: E402


@pytest.fixture
def exporter(tmp_path):
    """A CurveDataExporter writing to a throwaway directory."""
    return CurveDataExporter(output_dir=str(tmp_path / "data"))


@pytest.fixture
def make_pool():
    """Build a PoolData with sane defaults; override any field via kwargs."""

    def _make(**overrides):
        fields = dict(
            name="reUSD/scrvUSD",
            chain="ethereum",
            address="0xc522A6606BBA746d7960404F22a3DB936B6F4F50",
            tvl=1_000_000.0,
            base_apy=2.5,
            crv_rewards_apy=[3.43, 8.57],
            other_rewards=[],
            coins=["reUSD", "scrvUSD"],
            coin_ratios=["reUSD: 67.1%", "scrvUSD: 32.9%"],
            eth_amounts=[],
        )
        fields.update(overrides)
        return PoolData(**fields)

    return _make
