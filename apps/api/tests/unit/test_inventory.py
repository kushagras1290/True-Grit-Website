import pytest
from hypothesis import given
from hypothesis import strategies as st

from truegrit_api.domain.inventory import (
    InventoryLevel,
    availability_label,
    can_reserve,
    release,
    reserve,
    validate_movement,
)
from truegrit_api.errors import ValidationAppError

levels = st.builds(
    InventoryLevel,
    on_hand=st.integers(min_value=0, max_value=10_000),
    reserved=st.integers(min_value=0, max_value=10_000),
).filter(lambda level: level.reserved <= level.on_hand)


@given(level=levels, quantity=st.integers(min_value=1, max_value=10_000))
def test_reserved_never_exceeds_on_hand(level: InventoryLevel, quantity: int):
    if can_reserve(level, quantity):
        updated = reserve(level, quantity)
        assert updated.reserved <= updated.on_hand
        assert updated.available >= 0
    else:
        with pytest.raises(ValidationAppError):
            reserve(level, quantity)


def test_release_bounds():
    level = InventoryLevel(on_hand=10, reserved=4)
    assert release(level, 4).reserved == 0
    with pytest.raises(ValidationAppError):
        release(level, 5)
    with pytest.raises(ValidationAppError):
        release(level, 0)


def test_movement_direction_rules():
    validate_movement("receipt", 10)
    validate_movement("sale", -2)
    with pytest.raises(ValidationAppError):
        validate_movement("sale", 2)
    with pytest.raises(ValidationAppError):
        validate_movement("receipt", -1)
    with pytest.raises(ValidationAppError):
        validate_movement("teleport", 1)
    with pytest.raises(ValidationAppError):
        validate_movement("correction", 0)


def test_availability_labels():
    assert availability_label(InventoryLevel(0, 0), 5) == "out_of_stock"
    assert availability_label(InventoryLevel(4, 0), 5) == "low_stock"
    assert availability_label(InventoryLevel(50, 0), 5) == "in_stock"
    assert availability_label(InventoryLevel(10, 10), 5) == "out_of_stock"
