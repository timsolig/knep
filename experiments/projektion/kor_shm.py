"""Kör domaren med summorna i minnet (uppgift 0020), när disken är nästan full.

    uv run python experiments/projektion/kor_shm.py kör snabb utjamning_snabb:S_ab_b [...] [--dagar D ...]
    uv run python experiments/projektion/kor_shm.py tabell snabb utjamning_snabb:S_ab_b [...] [--ut fil.md]

domare.OUT sätts till /dev/shm/knep_domare. Referenserna (kedja_om, persistens) och 0019:s fryst variant
(utjamning_V_ab_f2_al95) kopieras dit ur /data/projektion/domare (några kB per dygn). Rörelsecachen
(/data/projektion/cache) skrivs inte: dess dygn finns redan; skriptet räknar filerna före och efter
och stannar om något har tillkommit. Inget skrivs till /data.
"""

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import domare as D  # noqa: E402

SHM = Path("/dev/shm/knep_domare")
REAL = D.OUT
KEEP = ["kedja_om", "persistens", "utjamning_V_ab_f2_al95"]


def cache_files() -> int:
    return sum(1 for p in D.CACHE.rglob("*") if p.is_file())


def prepare(mode: str) -> None:
    for name in KEEP:
        src, dst = REAL / mode / name, SHM / mode / name
        if src.exists() and not dst.exists():
            shutil.copytree(src, dst)


def main() -> None:
    cmd, mode, *rest = sys.argv[1:]
    out_file = None
    days = None
    if "--ut" in rest:
        i = rest.index("--ut")
        out_file = rest[i + 1]
        rest = rest[:i] + rest[i + 2:]
    if "--dagar" in rest:
        i = rest.index("--dagar")
        days = rest[i + 1:]
        rest = rest[:i]
    D.OUT = SHM
    SHM.mkdir(parents=True, exist_ok=True)
    prepare(mode)
    before = cache_files()
    if cmd == "kör":
        for s in rest:
            D.run(mode, s, 2, days)
    else:
        # dygnen som baslinjen har körts på (traning: de 12 dygnen från 0018, inte alla träningsdygn)
        have = {p.stem for p in (SHM / mode / "kedja_om").glob("*.npz")}
        full = D.mode_days
        D.mode_days = lambda m: [d for d in full(m) if d in have]
        md = D.table(mode, rest)
        print(md)
        if out_file:
            Path(out_file).write_text(md + "\n")
    after = cache_files()
    assert after == before, f"rörelsecachen ändrades: {before} -> {after}"
    print(f"rörelsecachen orörd ({after} filer)")


if __name__ == "__main__":
    main()
