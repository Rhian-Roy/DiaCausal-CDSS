"""Write config.json — the website's account-service settings — into the folder you deploy.

    cp -r web /tmp/site
    SUPABASE_URL=https://<ref>.supabase.co SUPABASE_PUBLISHABLE_KEY=sb_publishable_... \
        python scripts/web_config.py /tmp/site/config.json

The committed web/config.json says "accounts: off" (sign-in switched off, every page open) and must
never hold the key: the publishable key is public by design (every visitor's browser downloads it
and the database is protected by row-level security), but the project rule is "no API keys in this
public repo". So this script refuses to write into the repository's own web/ folder, and a test
checks the committed file.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

REPO_WEB = Path(__file__).resolve().parent.parent / "web"


def main(out: Path) -> int:
    if out.resolve().parent == REPO_WEB.resolve():
        print("Refusing to write the key into the repository (web/config.json is committed). "
              "Copy web/ to a deploy folder and write there.", file=sys.stderr)
        return 2
    url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    key = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "").strip()
    if not re.fullmatch(r"https://[a-z0-9]{20}\.supabase\.co", url):
        print("SUPABASE_URL must look like https://<20-letter ref>.supabase.co", file=sys.stderr)
        return 2
    if not key.startswith("sb_publishable_"):
        print("SUPABASE_PUBLISHABLE_KEY must be a publishable key (sb_publishable_...), never a secret key", file=sys.stderr)
        return 2
    out.write_text(json.dumps({"supabaseUrl": url, "supabaseKey": key}) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(main(Path(sys.argv[1])))
