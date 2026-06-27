"""Pytest bootstrap shared by the whole test suite.

Because this conftest.py lives at the project root, pytest puts the root on
sys.path, which makes `import course_reg` work no matter where pytest is
invoked from.

The DB-backed tests (test_logic_db.py, test_drop_or_swap_optionB.py) copy the
DB named by EVAL_SEED_DB to a temp file per test. If the env var is not set we
default it to the bundled seeded catalog so the suite runs out of the box.
Override it on the command line to point at a different seed DB.
"""

import os
from pathlib import Path

_ROOT = Path(__file__).parent
_DEFAULT_SEED_DB = _ROOT / "course_reg" / "sample_courses.db"

os.environ.setdefault("EVAL_SEED_DB", str(_DEFAULT_SEED_DB))
