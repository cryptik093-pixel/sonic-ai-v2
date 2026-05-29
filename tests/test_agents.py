from pathlib import Path

from app.agents.manager import AgentManager


def test_agent_create_and_generate_midi(tmp_path: Path):
    registry = tmp_path / "agents_registry.json"
    mgr = AgentManager(registry_path=registry)
    agent = mgr.create_agent("test_agent_1", role="musician", display_name="Test Musician")
    assert agent.agent_id == "test_agent_1"

    result = agent.run_task("generate_midi", prompt="dark trap melody at 140 bpm in D minor", seed=7)
    assert "midi_path" in result
    midi_path = Path(result["midi_path"])
    assert midi_path.exists()

    summary = agent.recall()
    assert summary["events_count"] >= 1
