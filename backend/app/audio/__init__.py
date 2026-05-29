"""Compatibility shim package for legacy imports.

Some modules in the codebase import from `app.audio.*` while the
implementation lives under `app.api.audio.*`. To maintain backwards
compatibility without refactoring many import sites, this package
provides thin re-exports of the API audio modules.

Note: keep this file minimal to avoid circular imports; individual
submodules are implemented as thin wrappers (loader.py, metrics.py,
etc.) to directly re-export from `app.api.audio`.
"""

__all__ = [
    "loader",
    "metrics",
    "engineering_report",
    "reference_profiles",
    "midi_generation",
    "prompt_to_midi",
    "audio_to_midi",
    "hybrid_transform",
    "production_advice",
    "magenta_bridge",
    "ai_tool_integrations",
]
