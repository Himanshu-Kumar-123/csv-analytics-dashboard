"""Errors raised by the data-processing layer (framework-agnostic)."""

from __future__ import annotations

from typing import Any


class DataError(Exception):
    def __init__(self, message: str, *, details: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class InvalidFileError(DataError):
    """The uploaded file is not an acceptable CSV."""


class InvalidParameterError(DataError):
    """A request parameter (column, filter, chart option...) is invalid for this dataset."""
