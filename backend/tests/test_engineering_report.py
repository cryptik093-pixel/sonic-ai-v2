import json

from app.audio.engineering_report import build_engineering_report


def test_report_builds_with_full_analysis_payload() -> None:
    report = build_engineering_report(_analysis_payload(), target_profile="modern_hiphop_master")

    assert set(report) == {
        "summary",
        "scorecard",
        "priority_moves",
        "mastering_chain",
        "mix_translation",
        "warnings",
        "export_layout",
        "metadata",
    }
    assert report["summary"]["overall_grade"] in {
        "excellent",
        "strong",
        "needs_work",
        "problematic",
        "unknown",
    }
    assert report["metadata"]["deterministic"] is True
    assert report["metadata"]["report_version"] == "engineering-report-0.1.0"


def test_report_does_not_crash_with_missing_metrics() -> None:
    report = build_engineering_report({"metrics": {}, "reference_comparison": {}})

    assert report["summary"]["confidence"] == "low"
    assert report["summary"]["overall_grade"] == "unknown"
    assert report["warnings"]


def test_loudness_score_changes_based_on_lufs_and_true_peak_values() -> None:
    stable_report = build_engineering_report(
        _analysis_payload(integrated_lufs=-10.0, true_peak_dbfs=-1.2)
    )
    risky_report = build_engineering_report(
        _analysis_payload(integrated_lufs=-6.5, true_peak_dbfs=-0.1)
    )

    assert risky_report["scorecard"]["loudness"] < stable_report["scorecard"]["loudness"]
    assert any(warning["code"] == "hot_true_peak" for warning in risky_report["warnings"])


def test_stereo_warning_appears_for_unsafe_stereo_correlation() -> None:
    report = build_engineering_report(_analysis_payload(stereo_correlation=-0.15))

    assert any(warning["code"] == "unsafe_stereo_correlation" for warning in report["warnings"])
    assert any(move["id"] == "fix_mono_compatibility" for move in report["priority_moves"])


def test_report_output_is_json_serializable() -> None:
    report = build_engineering_report(_analysis_payload())

    json.dumps(report)


def test_report_output_is_deterministic_for_identical_inputs() -> None:
    analysis = _analysis_payload()

    assert build_engineering_report(analysis) == build_engineering_report(analysis)


def test_export_layout_is_ordered_json_ready_and_renderable() -> None:
    report = build_engineering_report(
        _analysis_payload(
            integrated_lufs=-6.5,
            true_peak_dbfs=-0.1,
            high_mid_band_ratio=0.40,
        )
    )

    layout = report["export_layout"]

    assert layout["layout_version"] == "export-layout-0.1.0"
    assert layout["format"] == "single_page_sections"
    assert layout["title"] == "Sonic AI Engineering Report"
    assert layout["subtitle"] == "Target profile: modern_hiphop_master"
    assert layout["section_order"] == [section["id"] for section in layout["sections"]]
    assert [section["id"] for section in layout["sections"]] == [
        "cover_summary",
        "scorecard",
        "measured_metrics",
        "priority_moves",
        "mastering_chain",
        "translation_checks",
        "warnings_and_limits",
    ]
    assert all(section["title"] for section in layout["sections"])
    assert all(section["kind"] for section in layout["sections"])
    assert all(section["items"] for section in layout["sections"])
    assert any(
        item.startswith("critical: Create safer true-peak headroom")
        for section in layout["sections"]
        if section["id"] == "priority_moves"
        for item in section["items"]
    )


def test_mastering_chain_recommendation_changes_based_on_severity_and_grade() -> None:
    stable_report = build_engineering_report(_analysis_payload())
    corrective_report = build_engineering_report(
        _analysis_payload(
            integrated_lufs=-6.5,
            true_peak_dbfs=-0.1,
            crest_factor_db=3.0,
            dynamic_range_db=1.2,
            stereo_correlation=-0.2,
        )
    )

    assert stable_report["mastering_chain"]["chain_type"] == "clean_master"
    assert corrective_report["mastering_chain"]["chain_type"] == "corrective_mix_prep"


def test_scorecard_values_are_integers_from_zero_to_one_hundred() -> None:
    report = build_engineering_report(
        _analysis_payload(
            integrated_lufs=-4.0,
            true_peak_dbfs=0.5,
            crest_factor_db=1.0,
            dynamic_range_db=0.5,
            stereo_correlation=-0.8,
            stereo_width=1.3,
            sub_band_ratio=0.6,
            bass_band_ratio=0.4,
            high_band_ratio=0.01,
            high_mid_band_ratio=0.5,
        )
    )

    for score in report["scorecard"].values():
        assert isinstance(score, int)
        assert 0 <= score <= 100


def test_confidence_becomes_low_when_important_metrics_are_missing() -> None:
    report = build_engineering_report(
        {
            "metrics": {
                "integrated_lufs": -10.0,
                "true_peak_dbfs": -1.2,
            },
            "reference_comparison": {"deltas": [], "overall_severity": "none"},
        }
    )

    assert report["summary"]["confidence"] == "low"


def _analysis_payload(**metric_overrides: float) -> dict[str, object]:
    metrics = {
        "integrated_lufs": -10.0,
        "true_peak_dbfs": -1.2,
        "crest_factor_db": 10.0,
        "dynamic_range_db": 6.0,
        "clipping_ratio": 0.0,
        "stereo_correlation": 0.75,
        "stereo_width": 0.45,
        "side_energy_ratio": 0.15,
        "sub_band_ratio": 0.08,
        "bass_band_ratio": 0.18,
        "low_band_ratio": 0.18,
        "high_band_ratio": 0.18,
        "harsh_band_ratio": 0.10,
        "high_mid_band_ratio": 0.16,
        "mid_band_ratio": 0.50,
    }
    metrics.update(metric_overrides)
    return {
        "profile_id": "modern_hiphop_master",
        "metrics": metrics,
        "reference_comparison": {
            "profile_id": "modern_hiphop_master",
            "display_name": "Modern Hip-Hop Master",
            "overall_severity": "low",
            "deltas": [
                {
                    "metric_name": "integrated_lufs",
                    "measured": metrics["integrated_lufs"],
                    "target_min": -10.5,
                    "target_max": -8.0,
                    "delta_to_range": 0.0,
                    "direction": "inside_target",
                    "severity": "none",
                    "unit": "LUFS",
                }
            ],
            "strongest_issues": [],
        },
    }
