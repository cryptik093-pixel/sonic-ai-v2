# Sonic AI V2 API Contract

All API error responses are JSON. Success responses are JSON unless an endpoint explicitly documents a binary media type.

## GET `/health`

Returns service status.

Response:

```json
{
  "status": "ok",
  "service": "sonic-ai-v2-backend",
  "version": "0.1.0"
}
```

## POST `/api/v2/analyze`

Runs deterministic Sonic AI V2 audio analysis on an uploaded audio file.

Content type: `multipart/form-data`

Fields:

- `file`: required audio upload.
- `target_profile`: optional reference profile. Defaults to `modern_hiphop_master`.

`target_profile` may also be supplied as a query parameter.

Maximum upload size: 200 MB.

Supported formats:

- `.wav`
- `.wave`
- `.flac`
- `.aiff`
- `.aif`
- `.mp3`
- `.ogg`

Success response:

```json
{
  "status": "completed",
  "analysis": {
    "engine_version": "sonic-ai-v2-analysis-core-0.1.0",
    "filename": "mix.wav",
    "profile_id": "modern_hiphop_master",
    "metrics": {
      "integrated_lufs": -9.4,
      "true_peak_dbfs": -0.8
    },
    "reference_comparison": {
      "profile_id": "modern_hiphop_master",
      "display_name": "Modern Hip-Hop Master",
      "deltas": [],
      "overall_severity": "none",
      "strongest_issues": []
    },
    "engineering_report": {
      "summary": {
        "overall_grade": "strong",
        "short_verdict": "The mix is close, with a few focused engineering checks recommended.",
        "main_issue": null,
        "confidence": "high"
      },
      "scorecard": {
        "loudness": 92,
        "dynamics": 88,
        "low_end": 90,
        "stereo": 95,
        "spectral_balance": 87,
        "translation": 90
      },
      "priority_moves": [],
      "mastering_chain": {
        "chain_type": "clean_master",
        "recommended_chain": [
          "Corrective EQ",
          "Gentle bus compression",
          "Soft saturation",
          "Stereo safety check",
          "True peak limiter"
        ],
        "warning": null
      },
      "mix_translation": {
        "club_translation": "Low-end weight should translate on larger systems.",
        "phone_translation": "Midrange and loudness should remain readable on small speakers.",
        "car_translation": "Car playback should be a useful final check rather than a problem-finding step.",
        "mono_translation": "Mono fold-down risk is low from the available stereo measurements."
      },
      "warnings": [],
      "export_layout": {
        "layout_version": "export-layout-0.1.0",
        "format": "single_page_sections",
        "title": "Sonic AI Engineering Report",
        "subtitle": "Target profile: modern_hiphop_master",
        "section_order": [
          "cover_summary",
          "scorecard",
          "measured_metrics",
          "priority_moves",
          "mastering_chain",
          "translation_checks",
          "warnings_and_limits"
        ],
        "sections": [
          {
            "id": "cover_summary",
            "title": "Mix Review Summary",
            "kind": "summary",
            "items": [
              "Grade: strong.",
              "Confidence: high.",
              "The mix is close, with a few focused engineering checks recommended.",
              "Main issue: none detected."
            ]
          }
        ]
      },
      "metadata": {
        "deterministic": true,
        "report_version": "engineering-report-0.1.0",
        "limitations": [
          "Report is generated from deterministic audio metrics and fixed rule templates only.",
          "Recommendations are engineering checks, not a replacement for level-matched listening."
        ]
      }
    }
  }
}
```

Error response:

```json
{
  "status": "error",
  "error": {
    "code": "unsupported_audio_format",
    "message": "Unsupported audio file extension '.txt'. Supported formats: .aif, .aiff, .flac, .mp3, .ogg, .wav, .wave."
  }
}
```

Common error codes:

- `empty_file`
- `file_too_large`
- `audio_load_failed`
- `unsupported_audio_format`
- `unknown_target_profile`
- `invalid_request`
- `analysis_service_error`
- `analysis_failed`

Empty file example:

```json
{
  "status": "error",
  "error": {
    "code": "empty_file",
    "message": "Uploaded audio file is empty."
  }
}
```

Oversized file example:

```json
{
  "status": "error",
  "error": {
    "code": "file_too_large",
    "message": "Uploaded audio file exceeds the 200 MB limit."
  }
}
```

Corrupt audio example:

```json
{
  "status": "error",
  "error": {
    "code": "audio_load_failed",
    "message": "Uploaded audio could not be loaded: Could not load audio file 'upload.wav'."
  }
}
```

Unknown profile example:

```json
{
  "status": "error",
  "error": {
    "code": "unknown_target_profile",
    "message": "Unknown reference profile: 'unknown'."
  }
}
```

## POST `/api/v2/prompt-midi`

Generates deterministic MIDI from a text prompt using the local rule-based MIDI engine.

Request content type: `application/json`

Form-compatible clients may send `application/x-www-form-urlencoded` with `prompt`,
optional `seed`, and optional `format`.

Default success media type: `audio/midi`

Set `Accept: application/json` to receive MIDI bytes as base64 JSON plus the interpreted prompt metadata.

Request:

```json
{
  "prompt": "dark trap melody at 140 bpm in D minor",
  "seed": 12
}
```

`seed` is optional. The same prompt and seed must produce the same MIDI bytes.

Default success response headers:

- `X-Prompt`
- `X-Seed`
- `X-Key`
- `X-Mode`

JSON success response:

```json
{
  "status": "completed",
  "prompt": {
    "raw": "dark trap melody at 140 bpm in D minor",
    "seed": 12,
    "tempo_bpm": 140,
    "key": "D",
    "mode": "minor",
    "pattern_type": "melody",
    "density": "medium",
    "complexity": "moderate",
    "mood_modifiers": ["dark"],
    "primary_mood": "dark",
    "rhythm_style": "trap",
    "rhythm_grid": "eighth_hat_grid",
    "contour_rule": "low_narrow_minor_contour",
    "chord_degrees": [1, 6, 7, 5]
  },
  "midi": {
    "media_type": "audio/midi",
    "encoding": "base64",
    "byte_length": 123,
    "data_base64": "TVRoZ..."
  }
}
```

Error response:

```json
{
  "status": "error",
  "error": {
    "code": "empty_prompt",
    "message": "Prompt must not be empty."
  }
}
```

## POST `/api/v2/prompt-midi/download`

Generates deterministic MIDI from a text prompt and always returns a downloadable
MIDI file on success.

Request content type: `application/json` or `application/x-www-form-urlencoded`

Success media type: `audio/midi`

Request fields:

- `prompt`: required string
- `seed`: optional integer

Success response headers:

- `Content-Disposition`
- `Content-Length`
- `X-Prompt`
- `X-Seed`
- `X-Key`
- `X-Mode`

Error responses use the same JSON envelope as `POST /api/v2/prompt-midi`.
