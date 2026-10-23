"""Strict classifier for *genuinely unreadable files*, not ordinary Godot errors.

This helper deliberately requires a low-level read/decoding failure. Script parse
errors, missing resources, invalid references and runtime errors are not corruption.
Native UI must aggregate these results separately from Output/Debugger.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class FileReadFailure(str, Enum):
    IO_ERROR = "io_error"
    INVALID_ENCODING = "invalid_encoding"
    TRUNCATED_CONTAINER = "truncated_container"


@dataclass(frozen=True)
class CorruptFileFinding:
    path: str
    reason: str


def classify_file_read_failure(path: str, failure: FileReadFailure | str, detail: str = "") -> CorruptFileFinding | None:
    """Return one popup finding only for an explicit low-level read failure."""
    try:
        failure = FileReadFailure(failure)
    except ValueError:
        return None
    if not path or "\0" in path:
        return None
    reasons = {
        FileReadFailure.IO_ERROR: "No se pudo leer el archivo desde el almacenamiento.",
        FileReadFailure.INVALID_ENCODING: "El contenido no se puede decodificar como texto válido.",
        FileReadFailure.TRUNCATED_CONTAINER: "El contenedor del recurso está incompleto o truncado.",
    }
    reason = reasons[failure]
    if detail.strip():
        reason += " " + detail.strip()[:160]
    return CorruptFileFinding(path=path, reason=reason)


def group_corrupt_findings(findings: list[CorruptFileFinding]) -> list[CorruptFileFinding]:
    """Deduplicate by path, preserving first occurrence for a single grouped popup."""
    result: dict[str, CorruptFileFinding] = {}
    for finding in findings:
        result.setdefault(finding.path, finding)
    return [result[path] for path in sorted(result)]
