---
name: kymotip-plugin-dev
description: >
  Guide KymoTip GUI plugin development (custom StageWidgetBase measurement
  tabs distributed as a single folder under plugins/). Use when the user asks
  to create, modify, or debug a KymoTip plugin, asks how the plugin system
  works, or wants to package/share a plugin with lab members. Trigger on
  phrases like "KymoTipのプラグインを作って", "write a KymoTip plugin",
  "create a new measurement tab", or references to StageWidgetBase /
  kymotip.plugin_api.
---

# KymoTip Plugin Development

## Overview

KymoTip plugins are self-contained folders under `plugins/` that add a custom
measurement tab (e.g. cell shape, internal structure distribution) alongside
the built-in pipeline stages (00_raw–07_growth). The full specification —
the required `StageWidgetBase` contract, folder/naming rules, the
`kymotip.plugin_api` surface plugins are allowed to use, fault isolation
behavior, and how to share a plugin with lab members — lives in
[`references/PLUGIN_SPEC.md`](references/PLUGIN_SPEC.md). Do not
duplicate that content here; always read it fresh before writing or editing a
plugin, since it is the single source of truth for this skill.

A working reference implementation to copy as a template is bundled at
[`assets/plugin_examples/cell_shape_example_plugin/`](assets/plugin_examples/cell_shape_example_plugin/).
Copying and adapting this example is the fastest path for most new plugins.

## Workflow

1. Read `references/PLUGIN_SPEC.md` in full before doing anything else.
2. Read `assets/plugin_examples/cell_shape_example_plugin/__init__.py` as a
   concrete template for the `StageWidgetBase` subclass shape.
3. Create `plugins/<plugin_name>/__init__.py` (source checkout) — this path
   is already git-ignored, so it is safe to write into freely. For a
   packaged/installed KymoTip, the target is the OS user data directory
   instead (see PLUGIN_SPEC.md section 5, e.g.
   `%LOCALAPPDATA%\KymoTip\plugins` on Windows).
4. Implement one or more `StageWidgetBase` subclasses per the contract in
   PLUGIN_SPEC.md section 2 (`stage_title`, `plugin_order`, optional
   `tab_label` / `plugin_api_version`, and only `kymotip.plugin_api` imports —
   never reach into KymoTip internals directly).
5. Tell the user to restart the KymoTip GUI and enable the plugin from the
   toolbar's "Plugins" menu to verify it loads and appears as a tab.
6. If the user wants to share the plugin with lab members, follow the sharing
   convention in PLUGIN_SPEC.md (copy the whole folder — plugins are
   distributed as one folder per plugin, never a single file).

## Notes

- Single-file plugins are not supported; `__init__.py` plus optional helper
  modules in the same folder, imported with relative imports, is the only
  supported layout.
- Folders without `__init__.py`, or whose name starts with `_`, are ignored
  by the plugin loader.
- If `plugin_api_version` doesn't match `kymotip.plugin_api.PLUGIN_API_VERSION`,
  the plugin is silently skipped at load time — check this first if a new
  plugin doesn't appear in the Plugins menu.
