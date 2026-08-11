"""Exposes only the stable API that user plugins are allowed to use.

Plugins must not import `kymotip.core.*` or `kymotip.gui.*` internal
modules directly; always access them through this module instead. The
core/gui internals may be refactored in the future, but the names
re-exported here keep their compatibility.

See .claude/skills/kymotip-plugin-dev/references/PLUGIN_SPEC.md and
.claude/skills/kymotip-plugin-dev/assets/plugin_examples/ for the full
specification.
"""
from __future__ import annotations

# Version number used to reject a plugin at load time when its required
# API version doesn't match what this app provides. Bump this only on a
# breaking change.
PLUGIN_API_VERSION = 1

from .core.io_utils import (  # noqa: E402
    append_log,
    discover_frames,
    ensure_dir,
    frame_filename,
    frame_path,
    normalize_for_display,
    read_image_any,
    read_reference_image_size,
    save_xy_plot,
    write_image_any,
)
from .gui.stages.base import DirPicker, StageWidgetBase  # noqa: E402

__all__ = [
    "PLUGIN_API_VERSION",
    "StageWidgetBase",
    "DirPicker",
    "append_log",
    "discover_frames",
    "ensure_dir",
    "frame_filename",
    "frame_path",
    "normalize_for_display",
    "read_image_any",
    "read_reference_image_size",
    "save_xy_plot",
    "write_image_any",
]
