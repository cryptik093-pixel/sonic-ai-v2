import json

from app.cli import main


def test_cli_make_test_audio_and_analyze_round_trip(tmp_path, capsys) -> None:
    audio_path = tmp_path / "test_mix.wav"
    report_path = tmp_path / "analysis.json"

    assert main(["make-test-audio", "--output", str(audio_path), "--seconds", "1.0"]) == 0
    assert audio_path.exists()

    assert (
        main(
            [
                "analyze",
                "--input",
                str(audio_path),
                "--profile",
                "streaming_balanced",
                "--json-out",
                str(report_path),
            ]
        )
        == 0
    )
    payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert payload["status"] == "completed"
    assert payload["analysis"]["filename"] == "test_mix.wav"
    assert payload["analysis"]["profile_id"] == "streaming_balanced"

    captured = capsys.readouterr()
    assert '"status": "completed"' in captured.out


def test_cli_prompt_midi_writes_midi_and_metadata(tmp_path) -> None:
    midi_path = tmp_path / "prompt.mid"
    metadata_path = tmp_path / "prompt.json"

    assert (
        main(
            [
                "prompt-midi",
                "--prompt",
                "dark trap melody at 140 bpm in D minor",
                "--seed",
                "7",
                "--output",
                str(midi_path),
                "--json-out",
                str(metadata_path),
            ]
        )
        == 0
    )
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))

    assert midi_path.read_bytes().startswith(b"MThd")
    assert payload["status"] == "completed"
    assert payload["plan"]["parsed"]["tempo_bpm"] == 140
    assert payload["tracks"][0]["role"] == "melody"


def test_cli_audio_to_midi_writes_midi_and_metadata(tmp_path) -> None:
    audio_path = tmp_path / "test_mix.wav"
    midi_path = tmp_path / "extracted.mid"
    metadata_path = tmp_path / "extracted.json"

    main(["make-test-audio", "--output", str(audio_path), "--seconds", "1.0"])
    assert (
        main(
            [
                "audio-to-midi",
                "--input",
                str(audio_path),
                "--output",
                str(midi_path),
                "--json-out",
                str(metadata_path),
            ]
        )
        == 0
    )
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))

    assert midi_path.read_bytes().startswith(b"MThd")
    assert payload["status"] == "completed"
    assert payload["midi_bytes"] > 0
    assert payload["tracks"]
