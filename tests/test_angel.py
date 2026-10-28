from datetime import datetime, timedelta

import pytest

from historical_data.angel import INTERVALS, validate_range


def test_all_supported_intervals_have_explicit_limits():
    assert INTERVALS["1m"][1] == 30
    assert INTERVALS["1d"][1] == 2000


def test_ten_year_request_is_rejected():
    end = datetime(2026, 1, 1)
    with pytest.raises(ValueError, match="at most 2000 days"):
        validate_range("1d", end - timedelta(days=3652), end)


def test_valid_range_is_accepted():
    end = datetime(2026, 1, 1)
    validate_range("5m", end - timedelta(days=100), end)

