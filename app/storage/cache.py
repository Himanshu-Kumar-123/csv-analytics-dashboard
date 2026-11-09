"""Thread-safe LRU cache for loaded DataFrames."""

from __future__ import annotations

import threading
from collections import OrderedDict
from collections.abc import Hashable
from typing import Any


class LRUCache:
    def __init__(self, max_items: int) -> None:
        self.max_items = max(0, max_items)
        self._items: OrderedDict[Hashable, Any] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: Hashable) -> Any | None:
        with self._lock:
            if key not in self._items:
                return None
            self._items.move_to_end(key)
            return self._items[key]

    def put(self, key: Hashable, value: Any) -> None:
        if self.max_items == 0:
            return
        with self._lock:
            self._items[key] = value
            self._items.move_to_end(key)
            while len(self._items) > self.max_items:
                self._items.popitem(last=False)

    def invalidate(self, predicate: Any = None) -> None:
        with self._lock:
            if predicate is None:
                self._items.clear()
                return
            for key in [k for k in self._items if predicate(k)]:
                del self._items[key]

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, key: Hashable) -> bool:
        return key in self._items
