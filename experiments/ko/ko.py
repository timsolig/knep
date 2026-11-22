"""Kön: experiment som körs utan Claude, ett i taget, dygnet runt med låg prioritet.

    uv run python experiments/ko/ko.py kör        körskriptet (tjänsten knep-ko), går tills det stoppas
    uv run python experiments/ko/ko.py ett        kör nästa experiment i kön och avsluta
    uv run python experiments/ko/ko.py summera    skriv om sammanfattningen ur resultaten

Ett experiment är en JSON-fil i experiments/ko/ko/ (namnet bestämmer ordningen):

    {"id": "0001-ring-r24", "spar": "opera-ring", "syfte": "en mening",
     "kor": [["uv", "run", "python", "experiments/analys/a0o.py", "kor", "A0O_r24", "--del", "traning"], ...],
     "dom": {"domare": "analys", "fil": "/data/analys/domare_v2/tabell_A0O_r24_mot_A0_traning.json"},
     "max_min": 300}

"om_battre": ["id", ...] kör experimentet bara när de experimenten är klara och bättre enligt domaren
(annars "hoppad"), så att valideringen av en kandidat kan ligga i kön redan när sökningen läggs.

Ett tak (en fuskvariant som ser facit, "tak": true) räknas aldrig som en förbättring; dess största säkra
vinst är svaret på hur mycket en del av kedjan kan ge.

eller med prognosens domare:

     "dom": {"domare": "prognos", "läge": "snabb", "system": "modul:Klass", "ref": null}
     "dom": {"domare": "bortfall", "system": "kallor:FylldS", "mot": "fylld", "del": "traning"}

Kommandona i "kor" körs i tur och ordning i repots rot (ingen shell). Sedan sätts domen mekaniskt
ur domarens egen regel: analysens `verdict` (fältet "dom" i tabellens JSON) eller prognosens
`verdict` ur `compare`. Resultatet hamnar i /data/ko/resultat/<id>.json och sammanfattningen i
/data/ko/SAMMANFATTNING.md, som veckans genomgång läser (experiments/ko/vecka.md). Ett experiment
med ett resultat körs inte igen; ta bort resultatfilen för att köra om.

Mellan experimenten hämtar skriptet main (git merge --ff-only), så att en ny kö som slagits ihop
körs utan att någon behöver starta om. Testdelen kan inte nås härifrån: domarna har inget läge för den.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KO = ROOT / "experiments" / "ko" / "ko"
DATA = Path(os.environ.get("KO_DATA", "/data/ko"))
RES = DATA / "resultat"
LOGG = DATA / "logg"
SAMMAN = DATA / "SAMMANFATTNING.md"
VILA = int(os.environ.get("KO_VILA", "1800"))  # sekunder att vänta när kön är tom
MIN_DISK_GB = float(os.environ.get("KO_MIN_DISK_GB", "1.5"))


def nu() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%MZ")


def specs() -> list[dict]:
    out = []
    for p in sorted(KO.glob("*.json")):
        try:
            s = json.loads(p.read_text())
        except json.JSONDecodeError as e:
            out.append({"id": p.stem, "spar": "?", "fel": f"ogiltig JSON: {e}"})
            continue
        s.setdefault("id", p.stem)
        out.append(s)
    return out


def villkor(s: dict) -> str:
    """"kör", "vänta" eller "hoppa" för ett experiment med "om_battre": [id, ...] (körs bara om alla de
    experimenten är klara och bättre enligt domaren, till exempel valideringen efter träningen)."""
    for dep in s.get("om_battre", []):
        p = RES / f"{dep}.json"
        if not p.exists():
            return "vänta"
        if not (json.loads(p.read_text()).get("dom") or {}).get("battre"):
            return "hoppa"
    return "kör"


def nasta(alla: list[dict]) -> dict | None:
    for s in alla:
        if (RES / f"{s['id']}.json").exists():
            continue
        v = villkor(s)
        if v == "hoppa":
            spara({"id": s["id"], "spar": s.get("spar", "?"), "syfte": s.get("syfte", ""), "status": "hoppad",
                   "fel": f"inte bättre: {', '.join(s['om_battre'])}", "start": nu(), "slut": nu()})
            continue
        if v == "kör":
            return s
    return None


# ---------- domen ----------

def dom_analys(d: dict) -> dict:
    t = json.loads(Path(d["fil"]).read_text())
    v = t["dom"]
    rows = []
    for key, tab in t["tabell"].items():
        for name, r in tab.items():
            if isinstance(r, dict) and "diff" in r and r.get("lo") is not None:
                rows.append((f"{key} {name}", r))
    vinst = []
    for namn in v.get("battre_i", []):
        res, matt = namn.split(" ", 1)
        r = t["tabell"].get(f"{res}/alla", {}).get(matt)
        if r and r.get("lo") is not None:
            vinst.append((r["lo"], namn, r["diff"]))  # lo: den säkra delen av vinsten
    vinst.sort(reverse=True)
    return {"battre": bool(v["battre"]), "battre_i": v.get("battre_i", []), "samre_i": v.get("samre_i", []),
            "storsta_sakra_vinst": vinst[0][0] if vinst else 0.0,
            "storsta_vinst_i": vinst[0][1] if vinst else None, "dagar": len(t.get("dagar", []))}


def dom_prognos(d: dict) -> dict:
    sys.path.insert(0, str(ROOT / "experiments" / "projektion"))
    import domare  # noqa: PLC0415

    mode = d["läge"]
    ref = d.get("ref") or domare.LÄGEN[mode]["ref"]
    days = domare.mode_days(mode)
    ref_days = domare.load(mode, ref, days)
    sd = domare.load(mode, d["system"], days)
    if ref_days is None or sd is None:
        raise RuntimeError(f"summorna saknas för {d['system']} eller {ref} i {mode}")
    days = [x for x in days if ref_days[x]["issues"] > 0]
    cmp = domare.compare(sd, ref_days, days, nboot=1000)
    v, why = domare.verdict(cmp)
    vinst = []
    for k, r in cmp.items():
        if r["kind"] not in ("träff", "kons"):
            continue
        for i in [domare.LEADS.index(x) for x in domare.SHOW]:
            if domare.mark(r, i) == "*":
                vinst.append((float(-r["hi"][i]), f"{k}@{domare.LEADS[i] * 15}", float(-r["diff"][i])))
    vinst.sort(reverse=True)
    return {"battre": v == "bättre", "battre_i" if v == "bättre" else "samre_i": why,
            "storsta_sakra_vinst": vinst[0][0] if vinst else 0.0,
            "storsta_vinst_i": vinst[0][1] if vinst else None, "dagar": len(days)}


def dom_bortfall(d: dict) -> dict:
    """Bortfallsdomaren (experiments/bortfall/bortfallsdomare.py) har ingen samlad dom; här samma bootstrap
    per åldersklass, och bättre om FSS eller CSI är bättre i någon klass och inget mått sämre i någon."""
    sys.path.insert(0, str(ROOT / "experiments" / "bortfall"))
    import bortfallsdomare as B  # noqa: PLC0415

    las = lambda namn: json.loads((B.RESULTAT / d["del"] / f"{namn.replace(':', '_')}.json").read_text())  # noqa: E731
    a, b = B.per_dag(las(d["system"])), B.per_dag(las(d.get("mot", "fylld")))
    battre, samre, vinst = [], [], []
    for kl in range(len(B.KLASSER)):
        for k, r in B.bootstrap(a, b, kl).items():
            namn = f"{B.klassnamn(kl)} {k}"
            if r["dom"] == "sämre":
                samre.append(namn)
            elif r["dom"] == "bättre" and (k.startswith("fss") or k.startswith("csi")):
                battre.append(namn)
                vinst.append((r["lo"] if B.HOGRE_BATTRE[k] else -r["hi"], namn))
    vinst.sort(reverse=True)
    return {"battre": bool(battre) and not samre, "battre_i": battre, "samre_i": samre,
            "storsta_sakra_vinst": vinst[0][0] if vinst else 0.0, "storsta_vinst_i": vinst[0][1] if vinst else None,
            "dagar": len(set(a) & set(b))}


def doma(d: dict) -> dict:
    return {"analys": dom_analys, "prognos": dom_prognos, "bortfall": dom_bortfall}[d["domare"]](d)


# ---------- körningen ----------

def disk_gb(path: Path) -> float:
    st = os.statvfs(path)
    return st.f_bavail * st.f_frsize / 1e9


def kor_ett(s: dict) -> dict:
    LOGG.mkdir(parents=True, exist_ok=True)
    res = {"id": s["id"], "spar": s.get("spar", "?"), "syfte": s.get("syfte", ""), "tak": bool(s.get("tak")), "start": nu()}
    if "fel" in s:
        return res | {"status": "fel", "fel": s["fel"], "slut": nu()}
    t0 = time.monotonic()
    tidsgrans = 60 * int(s.get("max_min", 240))
    with open(LOGG / f"{s['id']}.txt", "a") as log:
        for argv in s.get("kor", []):
            kvar = tidsgrans - (time.monotonic() - t0)
            if kvar <= 0:
                return res | {"status": "tidsgräns", "slut": nu(), "minuter": round((time.monotonic() - t0) / 60)}
            log.write(f"\n===== {nu()} {' '.join(argv)}\n")
            log.flush()
            try:
                p = subprocess.run(argv, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=kvar,
                                   env=os.environ | {"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"})
            except subprocess.TimeoutExpired:
                return res | {"status": "tidsgräns", "slut": nu(), "minuter": round((time.monotonic() - t0) / 60)}
            if p.returncode != 0:
                return res | {"status": "fel", "fel": f"kod {p.returncode}: {' '.join(argv)}", "slut": nu(),
                              "minuter": round((time.monotonic() - t0) / 60)}
    res["minuter"] = round((time.monotonic() - t0) / 60)
    if "dom" not in s:
        return res | {"status": "klar", "slut": nu()}
    try:
        return res | {"status": "klar", "dom": doma(s["dom"]), "slut": nu()}
    except Exception as e:  # noqa: BLE001
        return res | {"status": "fel", "fel": f"domen: {e}", "slut": nu()}


def spara(res: dict) -> None:
    RES.mkdir(parents=True, exist_ok=True)
    (RES / f"{res['id']}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float) + "\n")


def hamta_main() -> None:
    subprocess.run(["git", "fetch", "-q", "origin", "main"], cwd=ROOT, check=False, timeout=120)
    subprocess.run(["git", "merge", "-q", "--ff-only", "origin/main"], cwd=ROOT, check=False, timeout=60)


# ---------- sammanfattningen ----------

def resultat() -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(RES.glob("*.json"))] if RES.exists() else []


def spar_lage(rs: list[dict]) -> dict:
    """Per spår: antal, antal bättre, största säkra vinst, och om de senaste tre inte har flyttat den."""
    out = {}
    for r in sorted(rs, key=lambda r: r.get("slut", "")):
        s = out.setdefault(r.get("spar", "?"), {"n": 0, "battre": 0, "basta": 0.0, "basta_id": None,
                                                "forsta": r.get("start"), "senaste": None, "vinster": []})
        s["n"] += 1
        s["senaste"] = r.get("slut")
        d = r.get("dom") or {}
        v = float(d.get("storsta_sakra_vinst") or 0.0)
        s["vinster"].append(v)
        if d.get("battre"):
            s["battre"] += 1
        if v > s["basta"]:
            s["basta"], s["basta_id"] = v, r["id"]
    for s in out.values():
        tidigare = max(s["vinster"][:-3], default=0.0)
        senaste = max(s["vinster"][-3:], default=0.0)
        # mättat: minst sex experiment, och de tre senaste har inte höjt det bästa med minst 20 % (och 0,005)
        s["mattat"] = s["n"] >= 6 and senaste < max(tidigare * 1.2, tidigare + 0.005)
        del s["vinster"]
    return out


def summera() -> str:
    rs = resultat()
    alla = specs()
    klara = {r["id"] for r in rs}
    kvar = [s for s in alla if s["id"] not in klara]
    lines = [f"# Kön, {nu()}", "",
             f"{len(rs)} experiment med resultat, {len(kvar)} kvar i kön. Ledigt på /data: {disk_gb(DATA if DATA.exists() else Path('/')):.1f} GB.", ""]
    ja = [r for r in rs if (r.get("dom") or {}).get("battre") and not r.get("tak")]
    lines += ["## Säkerställd förbättring", ""]
    lines += [f"- **{r['id']}** ({r['spar']}): {', '.join(r['dom'].get('battre_i', [])[:6])}; största säkra vinst "
              f"{r['dom']['storsta_sakra_vinst']:+.4f} i {r['dom']['storsta_vinst_i']}" for r in ja] or ["- ingen"]
    lines += ["", "## Spåren", "", "| spår | experiment | bättre | största säkra vinst | i | mättat? | sedan |", "|---|---|---|---|---|---|---|"]
    for namn, s in sorted(spar_lage(rs).items(), key=lambda kv: -kv[1]["basta"]):
        lines.append(f"| {namn} | {s['n']} | {s['battre']} | {s['basta']:+.4f} | {s['basta_id'] or '–'} | "
                     f"{'**ja**' if s['mattat'] else 'nej'} | {(s['forsta'] or '')[:10]} |")
    lines += ["", "## De senaste", "", "| id | spår | status | dom | min | säkert sämre i |", "|---|---|---|---|---|---|"]
    for r in sorted(rs, key=lambda r: r.get("slut", ""), reverse=True)[:25]:
        d = r.get("dom") or {}
        dom = "bättre" if d.get("battre") else ("inte bättre" if d else "–")
        dom = f"tak, {d.get('storsta_sakra_vinst', 0):+.4f} i {d.get('storsta_vinst_i')}" if r.get("tak") and d else dom
        lines.append(f"| {r['id']} | {r['spar']} | {r['status']}{' ' + r.get('fel', '') if r['status'] != 'klar' else ''} | "
                     f"{dom} | {r.get('minuter', '')} | {', '.join(d.get('samre_i', [])[:4])} |")
    lines += ["", "## Kvar i kön", ""] + ([f"- {s['id']} ({s.get('spar', '?')}): {s.get('syfte', '')}" for s in kvar] or ["- tom"])
    md = "\n".join(lines) + "\n"
    DATA.mkdir(parents=True, exist_ok=True)
    SAMMAN.write_text(md)
    return md


# ---------- huvudloopen ----------

def ett() -> bool:
    s = nasta(specs())
    if s is None:
        return False
    if disk_gb(DATA if DATA.exists() else Path("/")) < MIN_DISK_GB:
        print(f"{nu()} under {MIN_DISK_GB} GB ledigt, väntar", flush=True)
        return False
    print(f"{nu()} kör {s['id']} ({s.get('spar', '?')})", flush=True)
    res = kor_ett(s)
    spara(res)
    summera()
    print(f"{nu()} {s['id']}: {res['status']}"
          f"{' ' + ('bättre' if res.get('dom', {}).get('battre') else 'inte bättre') if 'dom' in res else ''}", flush=True)
    return True


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "kör"
    if cmd == "summera":
        print(summera())
    elif cmd == "ett":
        ett()
    elif cmd == "kör":
        egen = Path(__file__).resolve()
        mtid = egen.stat().st_mtime
        while True:
            hamta_main()
            if egen.stat().st_mtime != mtid:   # en ny ko.py från main: starta om med den (annars körs den gamla
                print(f"{nu()} ny ko.py, startar om", flush=True)   # koden vidare, som veckan 2026-11-20)
                os.execv(sys.executable, [sys.executable, str(egen), "kör"])
            if not ett():
                summera()
                time.sleep(VILA)
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
