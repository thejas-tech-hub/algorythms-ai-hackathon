"""Shared, validated JSON-loading utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError


ModelT = TypeVar("ModelT", bound=BaseModel)


class JsonDataError(ValueError):
    """Raised when a JSON data file cannot be read or does not match its model."""


def load_json_model(path: str | Path, model_type: type[ModelT]) -> ModelT:
    """Read *path* and validate the decoded JSON with a Pydantic model.

    Args:
        path: Location of the JSON data file.
        model_type: Pydantic model used to validate the decoded payload.

    Raises:
        FileNotFoundError: If *path* does not exist.
        JsonDataError: If the file cannot be decoded or does not validate.
    """
    data_path = Path(path)
    try:
        with data_path.open("r", encoding="utf-8") as data_file:
            payload: Any = json.load(data_file)
    except json.JSONDecodeError as error:
        raise JsonDataError(f"Invalid JSON in '{data_path}': {error.msg}") from error

    try:
        return model_type.model_validate(payload)
    except ValidationError as error:
        raise JsonDataError(f"Invalid data in '{data_path}': {error}") from error
