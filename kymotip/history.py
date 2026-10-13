"""Compact, append-only processing history shared by the GUI and plugins."""
from __future__ import annotations

import dataclasses
import json
import math
import os
import re
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any
from uuid import uuid4


HISTORY_FILENAME = "processing_history.jsonl"
HISTORY_API_VERSION = 1
_WRITE_LOCK = threading.Lock()


class HistoryError(RuntimeError):
    """The history cannot be saved; do not silently run without a record."""


def json_value(value: Any) -> Any:
    """Detach supported settings without stringifying arbitrary Python objects."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("History parameters must contain only finite numbers.")
        return value
    if isinstance(value, Path):
        return str(value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {field.name: json_value(getattr(value, field.name)) for field in dataclasses.fields(value)}
    if isinstance(value, Mapping):
        result = {}
        for key, item in value.items():
            if not isinstance(key, (str, int)):
                raise TypeError("History dictionary keys must be strings or integers.")
            key = str(key)
            if key in result:
                raise ValueError(f"Duplicate history key after conversion: {key}")
            result[key] = json_value(item)
        return result
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    if type(value).__module__.split(".")[0] == "numpy":
        import numpy as np

        if isinstance(value, np.generic):
            return json_value(value.item())
        if isinstance(value, np.ndarray) and value.size <= 1024:
            return json_value(value.tolist())
    raise TypeError(f"Unsupported history parameter type: {type(value).__name__}")


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


@dataclasses.dataclass(frozen=True)
class RunContext:
    """Read-only settings used by both the computation and its history record."""

    parameters: Mapping[str, Any]
    inputs: tuple
    outputs: tuple


@dataclasses.dataclass(frozen=True)
class TaskSpec:
    """Return from build_task; execute(context) must use the captured settings.

    Inputs/outputs describe series (directory, prefix/pattern, extension, role),
    never a per-frame filename list. Path values should be passed as Path objects.
    """

    execute: Callable[[RunContext], Any]
    parameters: Mapping[str, Any]
    inputs: Sequence[Mapping[str, Any]] = ()
    outputs: Sequence[Mapping[str, Any]] = ()
    requested_parameters: Mapping[str, Any] = dataclasses.field(default_factory=dict)
    parameter_schema_version: int = 1
    capture_mode: str = "explicit"

    def __post_init__(self):
        if not callable(self.execute):
            raise TypeError("TaskSpec.execute must be callable.")
        if not isinstance(self.parameters, Mapping):
            raise TypeError("TaskSpec.parameters must be a dictionary.")
        if not isinstance(self.requested_parameters, Mapping):
            raise TypeError("TaskSpec.requested_parameters must be a dictionary.")
        if type(self.parameter_schema_version) is not int or self.parameter_schema_version < 1:
            raise ValueError("parameter_schema_version must be a positive integer.")
        if self.capture_mode not in ("explicit", "ui_snapshot_only"):
            raise ValueError("Unknown history capture mode.")
        for series in (self.inputs, self.outputs):
            if isinstance(series, (str, bytes, Mapping)) or not isinstance(series, Sequence):
                raise TypeError("TaskSpec inputs/outputs must be sequences of series descriptions.")
            if any(not isinstance(item, Mapping) for item in series):
                raise TypeError("Each input/output series description must be a dictionary.")
        for field_name in ("parameters", "inputs", "outputs", "requested_parameters"):
            object.__setattr__(self, field_name, _freeze(json_value(getattr(self, field_name))))

    def __call__(self):
        """Execute captured settings; the GUI wraps this call with RecordedRun."""
        return self.execute(RunContext(self.parameters, self.inputs, self.outputs))


def series_info(directory, prefix="", extension="", *, role="input", **details) -> dict:
    """Build a compact description; resolve paths once before starting the task."""
    if not str(directory).strip():
        raise ValueError(f"The {role} directory is required.")
    return {"directory": str(Path(directory).resolve()), "prefix": prefix,
            "extension": extension.lstrip("."), "role": role, **details}


def summarize_frames(frames: Sequence[str]) -> list[dict]:
    """Summarize loaded SAM2 frames by series without enumerating filenames."""
    groups = {}
    for filename in frames:
        path = Path(filename).resolve()
        match = re.fullmatch(r"(.+)_(\d+)\.[^.]+", path.name)
        prefix = match[1] if match else ""
        key = (str(path.parent), prefix, path.suffix.lstrip("."))
        group = groups.setdefault(key, {"frame_count": 0, "first_frame": None, "last_frame": None})
        group["frame_count"] += 1
        if match:
            frame = int(match[2])
            group["first_frame"] = frame if group["first_frame"] is None else min(group["first_frame"], frame)
            group["last_frame"] = frame if group["last_frame"] is None else max(group["last_frame"], frame)
    return [series_info(directory, prefix, extension, role="images", **counts)
            for (directory, prefix, extension), counts in groups.items()]


def _record_paths(series: Sequence[Mapping], base: Path) -> list[dict]:
    result = []
    for source in series:
        item = json_value(source)
        if "directory" in item:
            directory = Path(item["directory"]).resolve()
            try:
                item["directory"] = directory.relative_to(base).as_posix()
                item["path_type"] = "project_relative"
            except ValueError:
                item["directory"] = str(directory)
                item["path_type"] = "absolute"
        result.append(item)
    return result


@contextmanager
def _locked_file(path: Path):
    # No sidecar lock file: both the OS lock and the thread lock protect this file.
    with _WRITE_LOCK, path.open("a+b") as stream:
        deadline = time.monotonic() + 5.0
        while True:
            try:
                stream.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise HistoryError("Processing history is locked by another process.")
                time.sleep(0.02)
        try:
            yield stream
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _check_tail(stream):
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    if not size:
        return
    stream.seek(-1, os.SEEK_END)
    if stream.read(1) != b"\n":
        raise HistoryError("Processing history has an incomplete final line. Preserve and repair the file before running.")
    position = size - 1
    tail = b""
    while position:
        length = min(4096, position)
        position -= length
        stream.seek(position)
        tail = stream.read(length) + tail
        if b"\n" in tail:
            tail = tail.rsplit(b"\n", 1)[1]
            break
    try:
        event = json.loads(tail.decode("utf-8"))
        if not isinstance(event, dict) or event.get("schema_version") != 1:
            raise ValueError("Unknown history format")
    except (ValueError, UnicodeError) as exc:
        raise HistoryError("Processing history has an invalid final record. The file was not changed.") from exc


def append_event(path: Path, event: Mapping) -> None:
    encoded = (json.dumps(json_value(event), ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    try:
        with _locked_file(path) as stream:
            _check_tail(stream)
            stream.seek(0, os.SEEK_END)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise HistoryError(f"Could not save processing history: {path}\n{exc}") from exc


class RecordedRun:
    """Start synchronously before dispatch; record outcome before GUI callbacks."""

    def __init__(self, spec: TaskSpec, base_dir, project_prefix: str, *, stage_id: str,
                 stage_name: str, stage_kind="builtin", plugin_version=None):
        if not str(base_dir).strip():
            raise HistoryError("Set the project base directory and apply it before running.")
        self.base = Path(base_dir).resolve()
        if not self.base.is_dir():
            raise HistoryError("The project base directory does not exist.")
        for output in spec.outputs:
            if "directory" in output and Path(output["directory"]).resolve() == self.base:
                raise HistoryError("Choose an output subfolder separate from the project base directory.")
        self.spec = spec
        self.path = self.base / HISTORY_FILENAME
        self.run_id = str(uuid4())
        self._finished = False
        self._executed = False
        from . import __version__

        event = {"schema_version": 1, "event": "run_started", "run_id": self.run_id,
                 "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                 "stage_id": stage_id, "stage_name": stage_name, "stage_kind": stage_kind,
                 "app_version": __version__, "plugin_version": plugin_version,
                 "project_base": str(self.base), "project_prefix": project_prefix,
                 "parameter_schema_version": spec.parameter_schema_version,
                 "capture_mode": spec.capture_mode, "parameters": spec.parameters,
                 "inputs": _record_paths(spec.inputs, self.base),
                 "outputs": _record_paths(spec.outputs, self.base)}
        if spec.requested_parameters:
            event["requested_parameters"] = spec.requested_parameters
        append_event(self.path, event)

    def finish(self, status: str):
        if self._finished:
            return
        if status not in ("success", "failed"):
            raise ValueError("Unknown processing status.")
        append_event(self.path, {"schema_version": 1, "event": "run_finished",
                                 "run_id": self.run_id, "status": status})
        self._finished = True

    def __call__(self):
        if self._executed or self._finished:
            raise RuntimeError("A recorded run can execute only once; create a new run for a retry.")
        self._executed = True
        try:
            result = self.spec()
        except Exception as processing_error:
            try:
                self.finish("failed")
            except Exception as history_error:
                raise HistoryError(f"Processing failed: {processing_error}\nHistory could not be saved: {history_error}") from processing_error
            raise
        try:
            self.finish("success")
        except Exception as exc:
            raise HistoryError(f"Processing succeeded, but its history could not be saved: {exc}") from exc
        return result
