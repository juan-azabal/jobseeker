"""
Helper for GitHub Actions: prints 'true' or 'false' based on user.active in a profile YAML.
Usage: python scripts/check_active.py config/profiles/juan.yaml
"""
import sys
import yaml

if len(sys.argv) < 2:
    print("true")
    sys.exit(0)

with open(sys.argv[1]) as f:
    p = yaml.safe_load(f)

active = p.get("user", {}).get("active", True)
print("true" if active else "false")
