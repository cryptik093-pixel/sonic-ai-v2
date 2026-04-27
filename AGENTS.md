# Sonic AI — AGENTS.md

## Mission
Stabilize Sonic AI as an analyzer-first public web app.

Required V1 flow:
1. User uploads audio
2. Backend analyzes audio
3. User receives a deterministic, grounded production report

## V1 scope lock
IN SCOPE:
- Flask app only
- upload endpoint
- analyze/status endpoint
- normalized analysis payload
- deterministic production/mix/master guidance generated only from measured findings
- basic UI that matches real backend routes
- local smoke test
- public deployment config

OUT OF SCOPE:
- auth
- credits
- user history
- generation/export
- live capture
- MIDI monitoring
- FastAPI/RQ
- any feature not required for upload -> analyze -> report

## Canonical files
- backend/app_factory.py
- backend/services/analysis.py
- backend/jobs.py
- backend/config.py
- templates/prototype.html
- validation/test_backend_analysis_contract.py

## Rules
- Read the canonical files first before editing.
- Do not invent routes, payload fields, or UI states.
- Do not create duplicate analyzer logic.
- Do not add new frameworks.
- Do not change scope.
- Do not claim something works unless verified by command output or tests.
- If uncertain, preserve working behavior and reduce risk.

## Output grounding rules
Every recommendation in the report must be tied to measured or derived findings.
Never hallucinate plugin chains or fixes.
If confidence is low, say so explicitly.
Use "insufficient evidence" instead of guessing.

Each report section must map to:
- finding
- why it matters
- recommended action
- caution

## Definition of done
Done means all of the following are true:
- health endpoint returns 200
- upload returns a valid job id and status
- analyze polling transitions correctly through pending/running/succeeded/failed
- successful analysis returns normalized JSON
- production report is deterministic and grounded in findings
- repeated requests do not loop endlessly
- same file hash reuses cached result when applicable
- prototype UI reflects actual backend routes and states
- app can be started locally with one documented command
- app has a production entrypoint for 

## Required work style
1. Inspect
2. Plan
3. Implement the smallest safe changes
4. Verify
5. Summarize exact file edits and exact commands run