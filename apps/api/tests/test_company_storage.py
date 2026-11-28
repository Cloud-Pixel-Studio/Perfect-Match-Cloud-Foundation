import pytest

from pmc_api.company_storage import UsageStatus, _capacity_status


@pytest.mark.parametrize(
    ("used", "limit", "available", "percent", "status"),
    [
        (1_000, None, None, None, "unconfigured"),
        (0, 1_000, 1_000, 0, "normal"),
        (799, 1_000, 201, 79, "normal"),
        (800, 1_000, 200, 80, "notice"),
        (899, 1_000, 101, 89, "notice"),
        (900, 1_000, 100, 90, "warning"),
        (999, 1_000, 1, 99, "warning"),
        (1_000, 1_000, 0, 100, "at_limit"),
        (1_001, 1_000, 0, 100, "over_limit"),
    ],
)
def test_capacity_status_uses_exact_thresholds(
    used: int,
    limit: int | None,
    available: int | None,
    percent: int | None,
    status: UsageStatus,
) -> None:
    assert _capacity_status(used, limit) == (available, percent, status)
