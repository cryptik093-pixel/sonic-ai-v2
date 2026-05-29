from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.logging import get_logger
from app.api.audio.prompt_to_midi import generate_prompt_midi, parse_prompt
from app.agents.memory import MemoryStore
from app.services.analyzer_service import AnalyzerService, analysis_result_to_dict
from app.services.mastering_service import MasteringService
from app.audio.production_advice import (
    generate_production_advice,
    production_advice_to_dict,
)
from app.audio.metrics import AudioMetrics
from app.audio.reference_profiles import ReferenceComparison, MetricDelta


logger = get_logger(__name__)


@dataclass
class Agent:
    agent_id: str
    role: str
    display_name: str
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    memory: MemoryStore = field(init=False)

    def __post_init__(self) -> None:
        self.memory = MemoryStore(self.agent_id)

    def remember(self, event_type: str, payload: Dict[str, Any]) -> None:
        logger.info("Agent remembering event", extra={"agent_id": self.agent_id, "type": event_type})
        self.memory.append_event(event_type, payload)

    def recall(self) -> Dict[str, Any]:
        return self.memory.summary()

    def run_task(self, task: str, **kwargs: Any) -> Dict[str, Any]:
        """Run a simple task. Supported tasks: 'generate_midi'.

        Returns a dict with task results and records the action in memory.
        """
        logger.info("Agent running task", extra={"agent_id": self.agent_id, "task": task})
        if task == "generate_midi":
            prompt = kwargs.get("prompt")
            seed = kwargs.get("seed")
            if not prompt:
                raise ValueError("generate_midi requires 'prompt' argument")

            result = generate_prompt_midi(prompt, seed=seed)

            # save midi to outputs/agents/<agent_id>/
            out_dir = Path("outputs/agents") / self.agent_id
            out_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
            safe_prompt = parse_prompt(prompt).raw_prompt.replace("/", "_").replace('"', "_")[:100]
            filename = f"agent_{self.agent_id}_midi_{timestamp}_{safe_prompt}_{'det' if seed is None else seed}.mid"
            path = out_dir / filename
            path.write_bytes(result.midi_bytes)

            payload = {
                "task": "generate_midi",
                "prompt": prompt,
                "seed": seed,
                "midi_path": str(path),
                "bytes": len(result.midi_bytes),
            }
            self.remember("task_run", payload)
            return payload

        if task == "analyze_audio":
            audio_path = kwargs.get("audio_path") or kwargs.get("path")
            profile_id = kwargs.get("profile_id", "modern_hiphop_master")
            if not audio_path:
                raise ValueError("analyze_audio requires 'audio_path' argument")

            analyzer = AnalyzerService()
            result = analyzer.analyze_file_path(audio_path, profile_id=profile_id)
            result_dict = analysis_result_to_dict(result)

            out_dir = Path("outputs/agents") / self.agent_id
            out_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
            filename = f"analysis_{timestamp}.json"
            path = out_dir / filename
            # write JSON analysis
            try:
                import json

                path.write_text(json.dumps(result_dict, indent=2))
            except Exception:
                # best-effort save; ignore write errors in memory payload
                pass

            payload = {
                "task": "analyze_audio",
                "audio_path": str(audio_path),
                "profile_id": profile_id,
                "analysis_path": str(path),
                "metrics": result_dict.get("metrics"),
            }
            self.remember("analysis_result", payload)
            return payload

        if task == "master_advice":
            # Provide deterministic mastering advice from an analysis result or audio path
            analysis = kwargs.get("analysis")
            audio_path = kwargs.get("audio_path")
            profile_id = kwargs.get("profile_id", "modern_hiphop_master")

            if analysis is None and audio_path is None:
                raise ValueError("master_advice requires 'analysis' or 'audio_path'")

            if analysis is None:
                analyzer = AnalyzerService()
                result = analyzer.analyze_file_path(audio_path, profile_id=profile_id)
                analysis = analysis_result_to_dict(result)

            # analysis expected to contain 'metrics' and 'reference_comparison'
            # If analysis came from AnalyzerService we should have dataclass instances
            # otherwise attempt to reconstruct dataclasses from plain dicts.
            if isinstance(analysis, dict):
                mdict = analysis.get("metrics") or {}
                cdict = analysis.get("reference_comparison") or {}
                try:
                    metrics_obj = AudioMetrics(**mdict)
                except Exception:
                    metrics_obj = None

                try:
                    deltas = [MetricDelta(**d) for d in cdict.get("deltas", [])]
                    strongest = [MetricDelta(**d) for d in cdict.get("strongest_issues", [])]
                    comparison_obj = ReferenceComparison(
                        profile_id=cdict.get("profile_id", ""),
                        display_name=cdict.get("display_name", ""),
                        deltas=deltas,
                        overall_severity=cdict.get("overall_severity", "none"),
                        strongest_issues=strongest,
                    )
                except Exception:
                    comparison_obj = None

                if metrics_obj is None or comparison_obj is None:
                    # Fallback: try to use raw dicts (some production advice functions
                    # accept mappings), but prefer dataclasses when possible.
                    advice = generate_production_advice(metrics=mdict, comparison=cdict)
                else:
                    advice = generate_production_advice(metrics=metrics_obj, comparison=comparison_obj)
            else:
                # analysis is likely a SonicAnalysisResult dataclass produced earlier
                metrics_obj = getattr(analysis, "metrics", None)
                comparison_obj = getattr(analysis, "reference_comparison", None)
                advice = generate_production_advice(metrics=metrics_obj, comparison=comparison_obj)
            advice_dict = production_advice_to_dict(advice)

            out_dir = Path("outputs/agents") / self.agent_id
            out_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
            filename = f"master_advice_{timestamp}.json"
            path = out_dir / filename
            try:
                import json

                path.write_text(json.dumps(advice_dict, indent=2))
            except Exception:
                pass

            payload = {
                "task": "master_advice",
                "analysis_reference": (analysis.get("filename") if isinstance(analysis, dict) else None),
                "advice_path": str(path),
                "advice": advice_dict,
            }
            self.remember("mastering_advice", payload)
            return payload

        raise NotImplementedError(f"Unsupported task: {task}")


class MasterAgent(Agent):
    def __init__(self, agent_id: str, display_name: str | None = None):
        super().__init__(agent_id=agent_id, role="master", display_name=display_name or "MasterAgent")


class StudioAgent(Agent):
    def __init__(self, agent_id: str, display_name: str | None = None):
        super().__init__(agent_id=agent_id, role="studio", display_name=display_name or "StudioAgent")


class MusicianAgent(Agent):
    def __init__(self, agent_id: str, display_name: str | None = None):
        super().__init__(agent_id=agent_id, role="musician", display_name=display_name or "MusicianAgent")
