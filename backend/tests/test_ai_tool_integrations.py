from app.audio.ai_tool_integrations import (
    MUSIC_AI_TOOL_INTEGRATIONS,
    get_music_ai_integration,
    list_music_ai_integrations,
)


def test_music_ai_integration_catalog_has_unique_ids() -> None:
    tool_ids = [tool.tool_id for tool in MUSIC_AI_TOOL_INTEGRATIONS]

    assert len(tool_ids) == len(set(tool_ids))


def test_core_runtime_keeps_heavy_or_incompatible_tools_out_of_default_dependencies() -> None:
    isolated_packages = {
        tool.package_name
        for tool in MUSIC_AI_TOOL_INTEGRATIONS
        if tool.status in {"blocked", "deferred", "sandbox_only"} and tool.package_name
    }

    assert "magenta" in isolated_packages
    assert "tensorflow" in isolated_packages
    assert "torchaudio" in isolated_packages


def test_v2_approved_optional_tools_are_grouped_for_music_lab_install() -> None:
    approved = list_music_ai_integrations("approved_optional")

    assert {tool.tool_id for tool in approved} == {"muspy", "scamp", "pydub"}
    assert all(tool.install_extra == "music-lab" for tool in approved)


def test_librosa_is_active_and_magenta_is_sandbox_only_for_v2_runtime() -> None:
    librosa = get_music_ai_integration("librosa")
    magenta = get_music_ai_integration("magenta")

    assert librosa.status == "active"
    assert magenta.status == "sandbox_only"
    assert "conflict" in magenta.reason.lower()
