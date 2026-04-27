from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def _load_module(module_name: str, relative_path: str):
    target = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, target)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError(f"Unable to load module from {target}")
    spec.loader.exec_module(module)
    return module


_ANALYZER_MODULE = _load_module("sonic_ai_compact_analyzer", "ai-engine/analyzer.py")
_GENERATION_MODULE = _load_module("sonic_ai_generation_server", "ai-engine/server.py")

compact_analysis = _ANALYZER_MODULE.compact_analysis
generate_pattern = _GENERATION_MODULE.generate_pattern
write_midi = _GENERATION_MODULE.write_midi
render_wav = _GENERATION_MODULE.render_wav
OUTPUT_DIR = _GENERATION_MODULE.OUTPUT_DIR
