from __future__ import annotations

from sqlalchemy import select

from app.extensions import db
from app.models import Dataset


class DatasetRepository:
    def add(self, dataset: Dataset) -> Dataset:
        db.session.add(dataset)
        db.session.commit()
        return dataset

    def get(self, dataset_id: str) -> Dataset | None:
        return db.session.get(Dataset, dataset_id)

    def list(self) -> list[Dataset]:
        return list(db.session.scalars(select(Dataset).order_by(Dataset.created_at.desc())))

    def delete(self, dataset: Dataset) -> None:
        db.session.delete(dataset)
        db.session.commit()
