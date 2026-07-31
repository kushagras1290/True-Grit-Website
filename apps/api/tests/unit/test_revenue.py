"""Farm revenue arithmetic.

Money rules get audited by the people they pay, so every one of them is
pinned here rather than left to the integration tests to imply.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from truegrit_api.domain.revenue import (
    MAX_COMMISSION_BPS,
    allocate_refund,
    format_commission_percent,
    net_revenue,
    parse_commission_percent,
    split_revenue,
    validate_commission_bps,
)
from truegrit_api.errors import ValidationAppError


class TestCommissionRate:
    @pytest.mark.parametrize(
        ("percent", "expected_bps"),
        [(0, 0), (15, 1500), (12.5, 1250), (7.25, 725), (100, 10_000), (0.01, 1)],
    )
    def test_percent_converts_to_basis_points(self, percent: float, expected_bps: int) -> None:
        assert parse_commission_percent(percent) == expected_bps

    def test_round_trips_through_display(self) -> None:
        assert format_commission_percent(parse_commission_percent(12.5)) == 12.5

    @pytest.mark.parametrize("percent", [-1, 101, 12.345, float("nan"), float("inf"), "15", None])
    def test_rejects_impossible_rates(self, percent: object) -> None:
        with pytest.raises(ValidationAppError):
            parse_commission_percent(percent)

    def test_true_is_not_one_basis_point(self) -> None:
        """`bool` subclasses `int` in Python, so an unguarded isinstance check
        would silently accept `True` as a commission rate."""
        with pytest.raises(ValidationAppError):
            validate_commission_bps(True)

    @pytest.mark.parametrize("basis_points", [-1, 10_001, 1.5, "1500"])
    def test_rejects_out_of_range_basis_points(self, basis_points: object) -> None:
        with pytest.raises(ValidationAppError):
            validate_commission_bps(basis_points)


class TestNetRevenue:
    def test_subtracts_refunds(self) -> None:
        assert net_revenue(100_00, 25_00) == 75_00

    def test_floors_at_zero_when_the_refund_exceeds_the_line(self) -> None:
        """A goodwill refund can exceed the goods value it is attached to.
        Going negative would make a later line silently subsidise it."""
        assert net_revenue(100_00, 250_00) == 0

    @pytest.mark.parametrize("value", [-1, 1.5, True, "100"])
    def test_rejects_non_money(self, value: object) -> None:
        with pytest.raises(ValidationAppError):
            net_revenue(value, 0)  # type: ignore[arg-type]


class TestSplit:
    def test_splits_at_the_stated_rate(self) -> None:
        split = split_revenue(1000_00, 1500)
        assert split.commission_minor == 150_00
        assert split.payout_minor == 850_00

    def test_zero_commission_pays_everything_to_the_farm(self) -> None:
        assert split_revenue(1000_00, 0).payout_minor == 1000_00

    def test_full_commission_pays_nothing_to_the_farm(self) -> None:
        split = split_revenue(1000_00, MAX_COMMISSION_BPS)
        assert (split.commission_minor, split.payout_minor) == (1000_00, 0)

    def test_rounding_favours_the_farm(self) -> None:
        """1 paisa at 15% is 0.15 paise of commission. Rounding the house's
        cut up would take a whole paisa for a fifteen-hundredth of one."""
        split = split_revenue(1, 1500)
        assert split.commission_minor == 0
        assert split.payout_minor == 1

    @given(
        net=st.integers(min_value=0, max_value=10_000_000_000),
        bps=st.integers(min_value=0, max_value=10_000),
    )
    def test_the_two_halves_always_reconstruct_the_whole(self, net: int, bps: int) -> None:
        """No paisa is created or destroyed between platform and farm, at any
        amount or rate. The payout is derived by subtraction precisely so this
        holds without a second rounding."""
        split = split_revenue(net, bps)
        assert split.commission_minor + split.payout_minor == net
        assert split.commission_minor >= 0
        assert split.payout_minor >= 0


class TestRefundAllocation:
    def test_single_farm_order_takes_the_whole_refund(self) -> None:
        assert allocate_refund(500_00, 1000_00, 1000_00) == 500_00

    def test_splits_by_share_of_order_value(self) -> None:
        """A ₹300 refund on a ₹1000 order where this farm supplied ₹400 of the
        goods lands ₹120 on that farm."""
        assert allocate_refund(300_00, 400_00, 1000_00) == 120_00

    def test_never_exceeds_the_line(self) -> None:
        assert allocate_refund(10_000_00, 100_00, 100_00) == 100_00

    def test_never_exceeds_the_refund_itself(self) -> None:
        """Found by the property test below. `order_gross` is the sum of the
        order's lines, so a line larger than it means the two were read
        inconsistently — without the second cap, that one line would be
        charged more than the whole refund."""
        assert allocate_refund(1, 2, 1) == 1

    def test_no_refund_means_no_allocation(self) -> None:
        assert allocate_refund(0, 400_00, 1000_00) == 0

    def test_zero_value_order_allocates_nothing(self) -> None:
        """Guards the division. A fully discounted order has no goods value to
        apportion against."""
        assert allocate_refund(100_00, 0, 0) == 0

    @given(
        refund=st.integers(min_value=0, max_value=1_000_000),
        line=st.integers(min_value=0, max_value=1_000_000),
        order=st.integers(min_value=1, max_value=1_000_000),
    )
    def test_allocation_is_bounded(self, refund: int, line: int, order: int) -> None:
        allocated = allocate_refund(refund, line, order)
        assert 0 <= allocated <= line
        assert allocated <= refund

    def test_shares_never_exceed_the_refund(self) -> None:
        """Rounding down per line means the shares can total slightly under the
        refund, never over — the platform absorbs the residue rather than
        over-charging whichever farm happens to sort first."""
        order_gross = 1000_00
        refund = 333_33
        lines = [333_00, 333_00, 334_00]
        allocated = [allocate_refund(refund, line, order_gross) for line in lines]
        assert sum(allocated) <= refund
