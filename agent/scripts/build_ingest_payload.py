"""Build JSON payload for Railway ingest from agent output file.

Called by GHA workflow — not imported by agent modules.

Usage:
    python build_ingest_payload.py <jobs_file> <output_tmpfile> [target_profile]

Reads the agent output JSON (v2 envelope or legacy bare array), writes
a combined payload to output_tmpfile, and prints the effective profile_id
to stdout.
"""

import json
import os
import sys


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <jobs_file> <output_tmpfile> [target_profile]", file=sys.stderr)
        sys.exit(1)

    jobs_file = sys.argv[1]
    tmpfile = sys.argv[2]
    target_profile = sys.argv[3] if len(sys.argv) > 3 else os.environ.get("TARGET_PROFILE", "")

    with open(jobs_file) as f:
        d = json.load(f)

    # v2 output: {"_metadata": {"profile_id": ...}, "jobs": [...]}
    # v1 legacy: bare JSON array
    file_profile = d.get("_metadata", {}).get("profile_id", "") if isinstance(d, dict) else ""
    effective = target_profile or file_profile

    jobs = d["jobs"] if isinstance(d, dict) and "jobs" in d else d
    payload = {"jobs": jobs}
    if effective:
        payload["profile_id"] = effective

    with open(tmpfile, "w") as f:
        json.dump(payload, f)

    print(effective)


if __name__ == "__main__":
    main()
