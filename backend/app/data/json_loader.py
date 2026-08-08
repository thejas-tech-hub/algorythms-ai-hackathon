"""Small JSON file-loading primitives used by the data repositories."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError


ModelT = TypeVar("ModelT", bound=BaseModel)
DATA_FILES_DIRECTORY = Path(__file__).resolve().parent / "files"


class JsonDataError(ValueError):
    """Raised when an application data file is unreadable or invalid."""


def load_json_file(filename: str) -> Any:
    """Load one JSON file from this package's ``files`` directory.

    ``filename`` must be a plain filename so callers cannot read outside the
    application data directory.
    """
    file_path = DATA_FILES_DIRECTORY / filename
    if Path(filename).name != filename:
        raise ValueError("filename must not contain a directory component")

    try:
        with file_path.open("r", encoding="utf-8") as source:
            return json.load(source)
    except json.JSONDecodeError as error:
        raise JsonDataError(f"Invalid JSON in '{file_path.name}': {error.msg}") from error


def load_json_model(filename: str, model_type: type[ModelT]) -> ModelT:
    """Load and validate a data file with the supplied Pydantic model."""
    try:
        return model_type.model_validate(load_json_file(filename))
    except ValidationError as error:
        raise JsonDataError(f"Invalid data in '{filename}': {error}") from error
