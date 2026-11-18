"""Kör A0B-varianterna efter varandra, en process per system (domaren delar A0-bilder mellan system).

    uv run python experiments/analys/a0b_kor.py BIT DEL UT LOGG SYSTEM [SYSTEM ...]
"""

import subprocess
import sys
from pathlib import Path

bit, del_, ut, logg, *systems = sys.argv[1:]
a0b = Path(__file__).resolve().parent / "a0b.py"
with open(logg, "a") as f:
    for s in systems:
        subprocess.run(
            ["timeout", "7200", sys.executable, str(a0b), "kor", s, "--del", del_, "--bit", bit, "--ut", ut],
            stdout=f, stderr=subprocess.STDOUT, check=False,
        )
