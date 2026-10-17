"""Write the server's OpenAPI schema to studio/src/api/openapi.json, so
`npm run types` (openapi-typescript) types the web app with the server's
own TagSpec, TagPlan, Target and Issue. Run with the ROOT venv:

    ../.venv/Scripts/python scripts/dump_openapi.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from aruco_studio.server.app import app  # noqa: E402

out = ROOT / "studio" / "src" / "api" / "openapi.json"
out.write_text(json.dumps(app.openapi(), indent=1, sort_keys=True) + "\n", encoding="utf-8",
               newline="\n")
print(out)
