"""Orchestrates storage, caching and the pure data-processing layer."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import IO

import pandas as pd
from flask import current_app

from app.core.filters import Condition, apply_filters, parse_filter_param, validate_conditions
from app.core.ingest import IngestLimits, parse_csv
from app.core.profiling import ColumnKind, build_schema
from app.errors import NotFoundError, PayloadTooLargeError
from app.models import Dataset
from app.services.samples import SAMPLES
from app.storage.cache import LRUCache
from app.storage.file_store import FileStore, FileTooLargeError
from app.storage.repository import DatasetRepository

logger = logging.getLogger(__name__)


@dataclass
class DatasetView:
    """A dataset with its (optionally filtered) DataFrame. Frames are read-only."""

    dataset: Dataset
    full: pd.DataFrame
    frame: pd.DataFrame
    conditions: list[Condition]
    kinds: dict[str, ColumnKind]

    @property
    def filter_summary(self) -> list[dict[str, object]]:
        return [c.to_dict() for c in self.conditions]


class DatasetService:
    def __init__(
        self,
        store: FileStore,
        repository: DatasetRepository,
        cache: LRUCache,
        *,
        limits: IngestLimits,
        max_upload_bytes: int,
        sample_dir: Path,
    ) -> None:
        self.store = store
        self.repository = repository
        self.cache = cache
        self.limits = limits
        self.max_upload_bytes = max_upload_bytes
        self.sample_dir = sample_dir
        self.filter_cache = LRUCache(2)

    # ---- ingestion -------------------------------------------------------
    def ingest_upload(self, stream: IO[bytes], filename: str, display_name: str) -> Dataset:
        try:
            staged, size = self.store.stage(stream, self.max_upload_bytes)
        except FileTooLargeError as exc:
            limit_mb = self.max_upload_bytes // (1024 * 1024)
            raise PayloadTooLargeError(f"File exceeds the {limit_mb} MB limit.") from exc
        return self._ingest(staged, size, filename, display_name, is_sample=False)

    def ingest_sample(self, key: str) -> Dataset:
        sample = SAMPLES.get(key)
        path = self.sample_dir / sample.filename if sample else None
        if sample is None or path is None or not path.is_file():
            raise NotFoundError(f"Sample dataset '{key}' was not found.")
        staged, size = self.store.stage_copy(path)
        return self._ingest(staged, size, sample.filename, sample.title, is_sample=True)

    def _ingest(
        self, staged: Path, size: int, filename: str, display_name: str, *, is_sample: bool
    ) -> Dataset:
        dataset_id = self.store.new_id()
        try:
            parsed = parse_csv(staged, self.limits)
            self.store.save(dataset_id, staged, parsed.df)
        except BaseException:
            self.store.discard(staged)
            raise
        dataset = Dataset(
            id=dataset_id,
            display_name=display_name,
            original_filename=filename,
            n_rows=len(parsed.df),
            n_cols=len(parsed.df.columns),
            size_bytes=size,
            encoding=parsed.encoding,
            delimiter=parsed.delimiter,
            schema=build_schema(parsed.df),
            is_sample=is_sample,
        )
        try:
            self.repository.add(dataset)
        except BaseException:
            self.store.delete(dataset_id)
            raise
        self.cache.put(dataset_id, parsed.df)
        logger.info(
            "Ingested dataset %s (%d rows x %d cols)", dataset_id, dataset.n_rows, dataset.n_cols
        )
        return dataset

    # ---- queries ---------------------------------------------------------
    def list(self) -> list[Dataset]:
        return self.repository.list()

    def get(self, dataset_id: str) -> Dataset:
        dataset = self.repository.get(dataset_id)
        if dataset is None:
            raise NotFoundError("Dataset not found.")
        return dataset

    def load_frame(self, dataset_id: str) -> pd.DataFrame:
        """Return the cached DataFrame. Callers must treat it as read-only."""
        self.get(dataset_id)
        df = self.cache.get(dataset_id)
        if df is None:
            if not self.store.exists(dataset_id):
                raise NotFoundError("Dataset files are missing.")
            df = self.store.load(dataset_id)
            self.cache.put(dataset_id, df)
        return df

    @staticmethod
    def kinds(dataset: Dataset) -> dict[str, ColumnKind]:
        return {c["name"]: c["kind"] for c in dataset.schema}

    def view(self, dataset_id: str, raw_filters: object = None) -> DatasetView:
        dataset = self.get(dataset_id)
        full = self.load_frame(dataset_id)
        kinds = self.kinds(dataset)
        conditions = validate_conditions(parse_filter_param(raw_filters), full, kinds)
        if not conditions:
            return DatasetView(dataset, full, full, conditions, kinds)
        key = (dataset_id, json.dumps([c.to_dict() for c in conditions], sort_keys=True))
        frame = self.filter_cache.get(key)
        if frame is None:
            frame = apply_filters(full, conditions)
            self.filter_cache.put(key, frame)
        return DatasetView(dataset, full, frame, conditions, kinds)

    def delete(self, dataset_id: str) -> None:
        dataset = self.get(dataset_id)
        self.repository.delete(dataset)
        self.store.delete(dataset_id)

        def belongs(key: object) -> bool:
            return key == dataset_id or (
                isinstance(key, tuple) and bool(key) and key[0] == dataset_id
            )

        self.cache.invalidate(belongs)
        self.filter_cache.invalidate(belongs)


def get_dataset_service() -> DatasetService:
    service = current_app.extensions.get("dataset_service")
    if service is None:
        cfg = current_app.config
        service = DatasetService(
            FileStore(cfg["DATA_DIR"]),
            DatasetRepository(),
            LRUCache(cfg["DATAFRAME_CACHE_SIZE"]),
            limits=IngestLimits(
                max_columns=cfg["MAX_COLUMNS"],
                max_header_length=cfg["MAX_HEADER_LENGTH"],
                max_cell_length=cfg["MAX_CELL_LENGTH"],
            ),
            max_upload_bytes=cfg["MAX_UPLOAD_MB"] * 1024 * 1024,
            sample_dir=Path(cfg["SAMPLE_DATA_DIR"]),
        )
        current_app.extensions["dataset_service"] = service
    return service
