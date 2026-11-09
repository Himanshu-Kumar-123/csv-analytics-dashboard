from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Dataset(db.Model):  # type: ignore[name-defined]
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    n_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    n_cols: Mapped[int] = mapped_column(Integer, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    encoding: Mapped[str] = mapped_column(String(32), nullable=False)
    delimiter: Mapped[str] = mapped_column(String(4), nullable=False)
    schema: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    is_sample: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    def to_dict(self, *, include_schema: bool = False) -> dict[str, Any]:
        created = self.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        data: dict[str, Any] = {
            "id": self.id,
            "name": self.display_name,
            "original_filename": self.original_filename,
            "rows": self.n_rows,
            "columns": self.n_cols,
            "size_bytes": self.size_bytes,
            "encoding": self.encoding,
            "delimiter": self.delimiter,
            "is_sample": self.is_sample,
            "created_at": created.isoformat(),
        }
        if include_schema:
            data["schema"] = self.schema
        return data
