# Magenta Sandbox

This folder is the Sonic AI V2 boundary for the local Magenta source zip:

`C:\Users\david someone\Downloads\magenta-main.zip`

Do not copy Magenta into `backend/app/` and do not import it from FastAPI
request handlers. The Magenta checkout is archived/inactive and pins dependency
versions that conflict with Sonic AI V2's current Python 3.12 backend.

Use this sandbox only for local research:

```powershell
cd "C:\Users\david someone\Desktop\sonic_ai_v2\sonic_ai_v2"
powershell -ExecutionPolicy Bypass -File .\tools\magenta_sandbox\extract_magenta.ps1
```

The script extracts the zip to:

`external\magenta-main`

`external/` is ignored by git so the production codebase does not absorb a large
third-party TensorFlow-era tree.

