"""
pytest configuration for agent/ test suite.

Adds the repository root to sys.path so that `shared/` (scoring_core,
master_cv_scoring, etc.) is importable when tests run from the agent/ directory,
matching the PYTHONPATH=$GITHUB_WORKSPACE setup used in CI.
"""

import sys
from pathlib import Path

# repo root is one level above agent/
_REPO_ROOT = str(Path(__file__).parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
