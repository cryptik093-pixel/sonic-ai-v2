from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.manager import AgentManager
from app.core.logging import get_logger


logger = get_logger(__name__)
router = APIRouter(tags=["agents"])

# Simple shared manager instance; lightweight and persisted to outputs/agents_registry.json
manager = AgentManager()


class CreateAgentRequest(BaseModel):
    agent_id: str = Field(description="Unique agent identifier")
    role: str = Field(default="musician", description="Role: master|studio|musician")
    display_name: Optional[str] = Field(default=None)


class RunTaskRequest(BaseModel):
    task: str = Field(description="Task name, e.g. 'generate_midi'")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict)


@router.post("/agents")
def create_agent(req: CreateAgentRequest):
    agent = manager.create_agent(req.agent_id, req.role, req.display_name)
    return {"agent_id": agent.agent_id, "role": agent.role, "display_name": agent.display_name}


@router.get("/agents")
def list_agents():
    agents = manager.list_agents()
    return [{"agent_id": a.agent_id, "role": a.role, "display_name": a.display_name} for a in agents.values()]


@router.get("/agents/{agent_id}")
def get_agent(agent_id: str):
    agent = manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="agent not found")
    return {
        "agent_id": agent.agent_id,
        "role": agent.role,
        "display_name": agent.display_name,
        "memory_summary": agent.recall(),
    }


@router.post("/agents/{agent_id}/task")
def run_agent_task(agent_id: str, req: RunTaskRequest):
    agent = manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="agent not found")
    try:
        result = agent.run_task(req.task, **(req.params or {}))
    except Exception as exc:
        logger.exception("agent task failed")
        raise HTTPException(status_code=500, detail=str(exc))
    return {"status": "ok", "result": result}


@router.get("/agents/{agent_id}/memory")
def agent_memory(agent_id: str, event_type: Optional[str] = None):
    agent = manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="agent not found")
    if event_type:
        events = [e.__dict__ for e in agent.memory.query_by_type(event_type)]
    else:
        events = [e.__dict__ for e in agent.memory.get_events()]
    return {"agent_id": agent.agent_id, "events": events}
