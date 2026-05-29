Sonic AI V2 FastMCP scaffold

This package contains a minimal FastAPI + FastMCP scaffold for Sonic AI V2.

How to run (development):

1. Create a virtualenv with Python 3.12
2. pip install -r backend\mcp_server\requirements.txt
3. uvicorn backend.mcp_server.server:app --reload --port 8000

- Health: GET /health
- Analyze: POST /api/v2/analyze (multipart/form-data file=...)
- Prompt→MIDI: POST /api/v2/prompt-midi (form/json prompt, optional seed)

MCP endpoint (if `mcp` is installed): mounted at /mcp
