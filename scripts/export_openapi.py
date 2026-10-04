"""Write openapi.json from the Pydantic models (the single source of truth for the API contract).

    .venv/bin/python scripts/export_openapi.py            # writes openapi.json at the repo root
    .venv/bin/python scripts/export_openapi.py --check    # exit 1 if openapi.json is stale

The 12 models of plan 8.4 plus the request/health/error wrappers also appear as components, so
web/types.d.ts (scripts/make_types.sh) covers every one of them.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from diacausal.api.contract_app import create_contract_app  # noqa: E402
from diacausal.api.schemas import MODELS  # noqa: E402

OUT = ROOT / "openapi.json"


def build() -> dict:
    spec = create_contract_app().openapi()
    # Models that no endpoint mentions directly (DriverV1 is only nested, the intermediate ones too)
    # are still components, because FastAPI collects every nested model; make sure all 12 are present.
    schemas = spec["components"]["schemas"]
    missing = [name for name in MODELS if name not in schemas]
    if missing:
        raise SystemExit(f"openapi.json is missing components: {missing}")
    return spec


def text(spec: dict) -> str:
    return json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv: list[str]) -> int:
    fresh = text(build())
    if "--check" in argv:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != fresh:
            print("openapi.json is stale: run  .venv/bin/python scripts/export_openapi.py", file=sys.stderr)
            return 1
        return 0
    OUT.write_text(fresh, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(build()['components']['schemas'])} schemas)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
