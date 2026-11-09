"""On-disk storage for uploaded datasets.

Layout: <data_dir>/<dataset_uuid>/{original.csv, data.parquet}. Paths are always
derived from server-generated UUIDs, never from user-supplied filenames.
"""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path
from typing import IO

import pandas as pd

from app.core.exceptions import InvalidFileError

CHUNK_SIZE = 1024 * 1024


class FileTooLargeError(Exception):
    pass


class FileStore:
    ORIGINAL = "original.csv"
    PARQUET = "data.parquet"

    def __init__(self, data_dir: str | Path) -> None:
        self.root = Path(data_dir).resolve()
        self.tmp = self.root / ".tmp"
        self.tmp.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def new_id() -> str:
        return str(uuid.uuid4())

    def dataset_dir(self, dataset_id: str) -> Path:
        try:
            canonical = str(uuid.UUID(dataset_id))
        except (ValueError, AttributeError, TypeError) as exc:
            raise ValueError("Invalid dataset id") from exc
        path = (self.root / canonical).resolve()
        if path.parent != self.root:
            raise ValueError("Invalid dataset id")
        return path

    def stage(self, stream: IO[bytes], max_bytes: int) -> tuple[Path, int]:
        """Stream an upload to a temp file, enforcing the size limit while writing."""
        path = self.tmp / f"{uuid.uuid4()}.upload"
        size = 0
        try:
            with path.open("wb") as out:
                while chunk := stream.read(CHUNK_SIZE):
                    size += len(chunk)
                    if size > max_bytes:
                        raise FileTooLargeError
                    out.write(chunk)
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        if size == 0:
            path.unlink(missing_ok=True)
            raise InvalidFileError("The file is empty.")
        return path, size

    def stage_copy(self, source: Path) -> tuple[Path, int]:
        path = self.tmp / f"{uuid.uuid4()}.upload"
        shutil.copyfile(source, path)
        return path, path.stat().st_size

    def save(self, dataset_id: str, staged_csv: Path, df: pd.DataFrame) -> None:
        target = self.dataset_dir(dataset_id)
        target.mkdir(parents=True, exist_ok=False)
        try:
            parquet_tmp = target / f"{self.PARQUET}.tmp"
            df.to_parquet(parquet_tmp, index=False)
            os.replace(parquet_tmp, target / self.PARQUET)
            os.replace(staged_csv, target / self.ORIGINAL)
        except BaseException:
            shutil.rmtree(target, ignore_errors=True)
            raise

    def load(self, dataset_id: str) -> pd.DataFrame:
        return pd.read_parquet(self.dataset_dir(dataset_id) / self.PARQUET)

    def exists(self, dataset_id: str) -> bool:
        try:
            return (self.dataset_dir(dataset_id) / self.PARQUET).is_file()
        except ValueError:
            return False

    def delete(self, dataset_id: str) -> None:
        shutil.rmtree(self.dataset_dir(dataset_id), ignore_errors=True)

    def discard(self, staged: Path) -> None:
        staged.unlink(missing_ok=True)
