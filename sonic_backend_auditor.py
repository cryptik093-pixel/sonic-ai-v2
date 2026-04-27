# Sonic Backend Auditor
# This script audits the backend for issues in the canonical analyzer-first path.

import json
from backend.app_factory import create_app
from backend.services.analysis import SonicAnalysisService

def audit_backend():
    """Audit the backend for compliance with V1 rules."""
    app = create_app()
    with app.test_client() as client:
        # Check /api/upload endpoint
        with open("test_audio.wav", "rb") as test_file:
            upload_response = client.post('/api/upload', data={"file": (test_file, "test.wav")})
        if upload_response.status_code != 201:
            print("/api/upload failed with status code", upload_response.status_code)
            return {"error": "/api/upload failed"}

        # Check /api/analyze endpoint
        job_id = upload_response.json.get("job_id")
        analyze_response = client.get(f'/api/analyze/{job_id}')
        if analyze_response.status_code != 200:
            print("/api/analyze failed with status code", analyze_response.status_code)
            return {"error": "/api/analyze failed"}

        # Validate JSON safety
        try:
            json.loads(analyze_response.data)
        except json.JSONDecodeError:
            print("/api/analyze returned invalid JSON")
            return {"error": "/api/analyze returned invalid JSON"}

        print("Backend audit passed.")
        return {"status": "passed"}

if __name__ == "__main__":
    result = audit_backend()
    print(result)