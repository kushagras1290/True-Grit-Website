from __future__ import annotations

import pytest

from truegrit_api.services.translation_batches import (
    _row_chunks,
    _task_insert_statement,
)


def test_multi_row_task_inserts_respect_d1s_100_bind_limit() -> None:
    row = tuple(str(index) for index in range(10))
    chunks = _row_chunks([row] * 31)

    assert [len(chunk) for chunk in chunks] == [10, 10, 10, 1]
    assert all(len(_task_insert_statement(chunk)[1]) <= 100 for chunk in chunks)


def test_oversized_task_insert_is_rejected_before_reaching_d1() -> None:
    row = tuple(str(index) for index in range(10))

    with pytest.raises(ValueError, match="bind limit"):
        _task_insert_statement([row] * 11)
