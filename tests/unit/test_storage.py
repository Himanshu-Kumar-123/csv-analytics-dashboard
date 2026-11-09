from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import pytest

from app.core.exceptions import InvalidFileError
from app.storage.cache import LRUCache
from app.storage.file_store import FileStore, FileTooLargeError


def test_stage_enforces_size_limit(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    with pytest.raises(FileTooLargeError):
        store.stage(io.BytesIO(b"x" * 101), max_bytes=100)
    assert list(store.tmp.iterdir()) == []


def test_stage_rejects_empty(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    with pytest.raises(InvalidFileError):
        store.stage(io.BytesIO(b""), max_bytes=100)


def test_save_load_delete_roundtrip(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    staged, size = store.stage(io.BytesIO(b"a\n1\n"), max_bytes=100)
    assert size == 4
    dataset_id = store.new_id()
    store.save(dataset_id, staged, pd.DataFrame({"a": [1]}))
    assert store.exists(dataset_id)
    assert (store.dataset_dir(dataset_id) / FileStore.ORIGINAL).read_bytes() == b"a\n1\n"
    assert store.load(dataset_id)["a"].tolist() == [1]
    store.delete(dataset_id)
    assert not store.exists(dataset_id)


@pytest.mark.parametrize("bad", ["../etc", "not-a-uuid", "", "..", "/tmp/x"])
def test_dataset_dir_rejects_non_uuid(tmp_path: Path, bad: str) -> None:
    store = FileStore(tmp_path)
    with pytest.raises(ValueError):
        store.dataset_dir(bad)
    assert store.exists(bad) is False


def test_lru_cache_evicts_oldest() -> None:
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.get("a") == 1  # a becomes most recent
    cache.put("c", 3)
    assert "b" not in cache
    assert cache.get("a") == 1
    assert cache.get("c") == 3


def test_lru_cache_invalidate_predicate() -> None:
    cache = LRUCache(5)
    cache.put(("ds1", "x"), 1)
    cache.put(("ds2", "x"), 2)
    cache.invalidate(lambda k: k[0] == "ds1")
    assert len(cache) == 1
    cache.invalidate()
    assert len(cache) == 0


def test_lru_cache_zero_size_stores_nothing() -> None:
    cache = LRUCache(0)
    cache.put("a", 1)
    assert cache.get("a") is None
