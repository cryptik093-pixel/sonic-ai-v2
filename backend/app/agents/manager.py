from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from app.agents.base import Agent, MasterAgent, StudioAgent, MusicianAgent


@dataclass
class AgentRecord:
    agent_id: str
    role: str
    display_name: str


class AgentManager:
    """In-memory registry with on-disk persistence for created agents."""

    def __init__(self, registry_path: Path | str | None = None):
        self.registry_path = Path(registry_path) if registry_path is not None else Path("outputs/agents_registry.json")
        self._agents: Dict[str, Agent] = {}
        self._load()

    def _load(self) -> None:
        if not self.registry_path.exists():
            return
        try:
            data = json.loads(self.registry_path.read_text())
            for rec in data.get("agents", []):
                agent_id = rec.get("agent_id")
                role = rec.get("role")
                name = rec.get("display_name")
                self._agents[agent_id] = self._create_instance(agent_id, role, name)
        except Exception:
            # ignore corrupted registry
            self._agents = {}

    def _save(self) -> None:
        payload = {"agents": [
            {"agent_id": a.agent_id, "role": a.role, "display_name": a.display_name}
            for a in self._agents.values()
        ]}
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self.registry_path.write_text(json.dumps(payload, indent=2))

    def _create_instance(self, agent_id: str, role: str, display_name: str | None = None) -> Agent:
        if role == "master":
            return MasterAgent(agent_id=agent_id, display_name=display_name)
        if role == "studio":
            return StudioAgent(agent_id=agent_id, display_name=display_name)
        return MusicianAgent(agent_id=agent_id, display_name=display_name)

    def create_agent(self, agent_id: str, role: str = "musician", display_name: Optional[str] = None) -> Agent:
        if agent_id in self._agents:
            return self._agents[agent_id]
        agent = self._create_instance(agent_id, role, display_name)
        self._agents[agent_id] = agent
        self._save()
        return agent

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        return self._agents.get(agent_id)

    def list_agents(self) -> Dict[str, Agent]:
        return dict(self._agents)
