"""Marshmallow schemas for validating query strings and JSON bodies."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from marshmallow import EXCLUDE, Schema, fields, validate
from marshmallow import ValidationError as MarshmallowValidationError

from app.errors import ValidationError


def load(schema: Schema, data: Mapping[str, Any]) -> dict[str, Any]:
    try:
        return schema.load(data)
    except MarshmallowValidationError as exc:
        raise ValidationError("Invalid request parameters.", details=exc.messages) from exc


class BaseSchema(Schema):
    class Meta:
        unknown = EXCLUDE


class FilterQuerySchema(BaseSchema):
    filters = fields.String(load_default=None)


class PreviewQuerySchema(FilterQuerySchema):
    page = fields.Integer(load_default=1, validate=validate.Range(min=1))
    page_size = fields.Integer(load_default=50, validate=validate.Range(min=1, max=200))
    sort = fields.String(load_default=None)
    order = fields.String(load_default="asc", validate=validate.OneOf(["asc", "desc"]))


class ValuesQuerySchema(FilterQuerySchema):
    top = fields.Integer(load_default=20, validate=validate.Range(min=1, max=100))


class CorrelationQuerySchema(FilterQuerySchema):
    method = fields.String(load_default="pearson", validate=validate.OneOf(["pearson", "spearman"]))


class DuplicatesQuerySchema(FilterQuerySchema):
    columns = fields.String(load_default=None)
    normalize = fields.Boolean(load_default=False)
    max_groups = fields.Integer(load_default=20, validate=validate.Range(min=1, max=100))
