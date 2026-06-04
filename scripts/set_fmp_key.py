"""Foolproof FMP_API_KEY setter.

Prompts for the key with `getpass` (no echo, no shell history), then writes
or updates the FMP_API_KEY line in the project's .env file.

Usage:
    cd ~/Desktop/crypto-trends
    uv run python scripts/set_fmp_key.py
"""

from __future__ import annotations

import getpass
import sys
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
EXAMPLE_PATH = Path(__file__).resolve().parent.parent / ".env.example"


def main() -> int:
    if not ENV_PATH.exists():
        if EXAMPLE_PATH.exists():
            ENV_PATH.write_text(EXAMPLE_PATH.read_text())
            print(f"Created {ENV_PATH} from .env.example")
        else:
            ENV_PATH.write_text("")
            print(f"Created empty {ENV_PATH}")

    try:
        key = getpass.getpass("Paste your NEW FMP_API_KEY (input is hidden, "
                              "won't appear on screen): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nAborted.")
        return 1

    if not key:
        print("No key entered, aborting.")
        return 1
    if len(key) < 10:
        print(f"That looks too short ({len(key)} chars). Aborting — re-run when ready.")
        return 1

    lines = ENV_PATH.read_text().splitlines()
    found = False
    for i, line in enumerate(lines):
        if line.startswith("FMP_API_KEY="):
            lines[i] = f"FMP_API_KEY={key}"
            found = True
            break
    if not found:
        lines.append(f"FMP_API_KEY={key}")

    # Trailing newline so the file is well-formed.
    ENV_PATH.write_text("\n".join(lines) + "\n")
    print(
        f"Updated .env. FMP_API_KEY fingerprint: "
        f"len={len(key)}, starts={key[:3]}…, ends=…{key[-3:]}"
    )
    print("Key never appeared on screen, never stored in shell history.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
