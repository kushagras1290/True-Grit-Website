import pytest
from hypothesis import given
from hypothesis import strategies as st

from truegrit_api.domain.money import (
    MAX_AMOUNT_MINOR,
    apply_discount,
    basis_points_discount,
    effective_unit_price,
    line_total,
    validate_amount,
)
from truegrit_api.errors import ValidationAppError

amounts = st.integers(min_value=0, max_value=MAX_AMOUNT_MINOR)
bps = st.integers(min_value=0, max_value=10_000)


def test_rejects_floats_and_negatives():
    with pytest.raises(ValidationAppError):
        validate_amount(-1)
    with pytest.raises(ValidationAppError):
        validate_amount(89.9)  # type: ignore[arg-type]
    with pytest.raises(ValidationAppError):
        validate_amount(True)  # type: ignore[arg-type]


def test_basis_points_examples():
    assert basis_points_discount(89900, 1000) == 8990  # 10% of ₹899
    assert basis_points_discount(89900, 1000, maximum_discount_minor=5000) == 5000
    assert basis_points_discount(0, 10_000) == 0


@given(amount=amounts, points=bps)
def test_discount_never_exceeds_amount(amount: int, points: int):
    discount = basis_points_discount(amount, points)
    assert 0 <= discount <= amount


@given(amount=amounts, discount=amounts)
def test_total_never_negative(amount: int, discount: int):
    assert apply_discount(amount, discount) >= 0


@given(amount=st.integers(min_value=0, max_value=10_000_00), quantity=st.integers(1, 50))
def test_line_total_multiplies(amount: int, quantity: int):
    assert line_total(amount, quantity) == amount * quantity


def test_effective_price_prefers_valid_sale():
    assert effective_unit_price(89900, None) == 89900
    assert effective_unit_price(89900, 74900) == 74900
    with pytest.raises(ValidationAppError):
        effective_unit_price(89900, 99900)
