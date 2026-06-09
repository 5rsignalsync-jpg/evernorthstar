"""Multi-key launch helper. Prompts (hidden input, no shell history, no chat
leak) for the 5 launch values:

  1. Stripe secret key
  2. Stripe MONTHLY price ID
  3. Stripe ANNUAL price ID
  4. Gmail sender address (the FROM address — not hidden, you already shared)
  5. Gmail App Password (16-char, hidden)

Any prompt you press Enter on without typing is SKIPPED — the existing .env
value (or blank) is preserved. So you can run this multiple times as you
collect each value, you don't have to have all 5 at once.

After saving, prints a fingerprint of each value (first 3 + last 3 chars) so
you (and Claude) can verify the keys landed without ever seeing them in full.
"""

from __future__ import annotations

import getpass
import re
import sys
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
EXAMPLE_PATH = Path(__file__).resolve().parent.parent / ".env.example"


def _ensure_env_exists() -> None:
    if ENV_PATH.exists():
        return
    if EXAMPLE_PATH.exists():
        ENV_PATH.write_text(EXAMPLE_PATH.read_text())
        print(f"Created {ENV_PATH} from .env.example")
    else:
        ENV_PATH.write_text("")
        print(f"Created empty {ENV_PATH}")


def _read_env() -> dict[str, str]:
    out: dict[str, str] = {}
    if not ENV_PATH.exists():
        return out
    for line in ENV_PATH.read_text().splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip()
    return out


def _write_env(values: dict[str, str]) -> None:
    """Preserve original ordering + comments; only update / append known keys."""
    lines = ENV_PATH.read_text().splitlines() if ENV_PATH.exists() else []
    seen = set()
    out_lines: list[str] = []
    for line in lines:
        if line and not line.startswith("#") and "=" in line:
            key, _, _ = line.partition("=")
            key = key.strip()
            if key in values:
                out_lines.append(f"{key}={values[key]}")
                seen.add(key)
                continue
        out_lines.append(line)
    # Append any new keys that weren't already in the file.
    for key, val in values.items():
        if key in seen:
            continue
        out_lines.append(f"{key}={val}")
    ENV_PATH.write_text("\n".join(out_lines) + "\n")


def _fingerprint(value: str) -> str:
    if not value:
        return "<blank>"
    if len(value) <= 6:
        return "<too short to fingerprint>"
    return f"len={len(value)}  {value[:3]}…{value[-3:]}"


def _prompt_hidden(label: str, current_fingerprint: str) -> str | None:
    """Returns the new value, or None if user pressed Enter to skip."""
    print()
    print(f"  ── {label}")
    print(f"     current: {current_fingerprint}")
    try:
        new = getpass.getpass(
            "     paste new value (or just Enter to skip · input is hidden): "
        )
    except (EOFError, KeyboardInterrupt):
        print("\n     aborted by user")
        return None
    new = new.strip()
    # Gmail app passwords come with spaces; strip them safely.
    new = re.sub(r"\s+", "", new)
    if not new:
        return None
    return new


def _prompt_visible(label: str, current_value: str) -> str | None:
    """For non-secret values like the sender email address."""
    print()
    print(f"  ── {label}")
    print(f"     current: {current_value or '<blank>'}")
    try:
        new = input("     paste new value (or just Enter to skip): ")
    except (EOFError, KeyboardInterrupt):
        print("\n     aborted by user")
        return None
    new = new.strip()
    if not new:
        return None
    return new


KEYS_HIDDEN = [
    ("STRIPE_SECRET_KEY", "Stripe Secret key (starts sk_test_… or sk_live_…)"),
    ("STRIPE_PRICE_PRO_MONTHLY", "Stripe MONTHLY price ID (starts price_…)"),
    ("STRIPE_PRICE_PRO_ANNUAL", "Stripe ANNUAL price ID (starts price_…)"),
    ("GMAIL_APP_PASSWORD", "Gmail App Password (16 chars, spaces OK)"),
]

KEYS_VISIBLE = [
    ("GMAIL_ADDRESS", "Gmail sender address (e.g. yourname@gmail.com)"),
]


def main() -> int:
    _ensure_env_exists()
    existing = _read_env()

    print()
    print("=" * 60)
    print("  TheEverNorthstar — launch key setup")
    print("  No values are printed back; nothing reaches the chat.")
    print("  Press Enter on any prompt to skip / keep current.")
    print("=" * 60)

    updates: dict[str, str] = {}

    for key, label in KEYS_HIDDEN:
        current = existing.get(key, "")
        new = _prompt_hidden(label, _fingerprint(current))
        if new is not None:
            updates[key] = new

    for key, label in KEYS_VISIBLE:
        current = existing.get(key, "")
        new = _prompt_visible(label, current)
        if new is not None:
            updates[key] = new

    if not updates:
        print()
        print("No changes. Nothing written.")
        return 0

    _write_env(updates)

    print()
    print("─" * 60)
    print("  Saved. Fingerprints (so Claude can confirm without seeing values):")
    print("─" * 60)
    for key in [k for k, _ in KEYS_HIDDEN] + [k for k, _ in KEYS_VISIBLE]:
        if key in updates:
            print(f"  {key} → {_fingerprint(updates[key])}")
    print()
    print("  All values landed in .env. Tell Claude 'keys saved' to continue.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
