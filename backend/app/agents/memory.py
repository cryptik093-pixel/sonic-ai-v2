from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class MemoryEvent:
    timestamp: str
    type: str
    payload: Dict[str, Any]


class MemoryStore:
    """Simple file-backed JSON memory store per agent.

    Stores an append-only list of events under `outputs/agents_memory/<agent_id>.json`.
    """

    def __init__(self, agent_id: str, base_dir: Path | str | None = None):
        self.agent_id = agent_id
        self.base_dir = Path(base_dir) if base_dir is not None else Path("outputs/agents_memory")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.base_dir / f"agent_{agent_id}.json"
        self._events: List[MemoryEvent] = []
        self._loaded = False

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def load(self) -> None:
        if self._loaded:
            return
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text())
                self._events = [MemoryEvent(**e) for e in data.get("events", [])]
            except Exception:
                # corrupted store: reset to empty
                self._events = []
        else:
            self._events = []
        self._loaded = True

    def save(self) -> None:
        payload = {"agent_id": self.agent_id, "events": [e.__dict__ for e in self._events]}
        self.path.write_text(json.dumps(payload, indent=2))

    def append_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        self.load()
        ev = MemoryEvent(timestamp=self._now_iso(), type=event_type, payload=payload)
        self._events.append(ev)
        self.save()

    def get_events(self) -> List[MemoryEvent]:
        self.load()
        return list(self._events)

    def query_by_type(self, event_type: str) -> List[MemoryEvent]:
        self.load()
        return [e for e in self._events if e.type == event_type]

    def summary(self) -> Dict[str, Any]:
        self.load()
        counts: Dict[str, int] = {}
        for e in self._events:
            counts[e.type] = counts.get(e.type, 0) + 1
        return {"agent_id": self.agent_id, "events_count": len(self._events), "by_type": counts}
