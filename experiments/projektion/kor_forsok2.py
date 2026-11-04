"""De baslinjer som inte hann köras i försök 1, i validering_gles (fortsätter från sparade dygn).

    uv run python experiments/projektion/kor_forsok2.py /data/projektion/logg/baslinjer.log
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import domare as D  # noqa: E402

PLAN = ["pysteps", "kedja_utan_matchning", "sprog"]

if __name__ == "__main__":
    if len(sys.argv) > 1:
        sys.stdout = sys.stderr = open(sys.argv[1], "a", buffering=1)
    print("===== försök 2", time.strftime("%H:%M:%S"))
    names = sys.argv[2:] or PLAN
    for name in names:
        D.run("validering_gles", name, 2, None)
