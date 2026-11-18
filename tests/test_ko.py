"""Kön (experiments/ko/ko.py): ordningen, körningen, domen ur analysens tabell och spårens mättnad."""

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _ko(tmp_path, monkeypatch):
    monkeypatch.setenv("KO_DATA", str(tmp_path / "data"))
    spec = importlib.util.spec_from_file_location("ko_test", ROOT / "experiments/ko/ko.py")
    ko = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ko)
    ko.KO = tmp_path / "ko"
    ko.KO.mkdir()
    return ko


def test_ordning_och_hoppar_over_klara(tmp_path, monkeypatch):
    ko = _ko(tmp_path, monkeypatch)
    for n in ("0002-b", "0001-a"):
        (ko.KO / f"{n}.json").write_text(json.dumps({"spar": "x", "kor": []}))
    assert ko.nasta(ko.specs())["id"] == "0001-a"
    ko.spara({"id": "0001-a", "status": "klar"})
    assert ko.nasta(ko.specs())["id"] == "0002-b"


def test_kor_fel_och_tidsgrans(tmp_path, monkeypatch):
    ko = _ko(tmp_path, monkeypatch)
    ok = ko.kor_ett({"id": "a", "kor": [[sys.executable, "-c", "print(1)"]]})
    fel = ko.kor_ett({"id": "b", "kor": [[sys.executable, "-c", "raise SystemExit(3)"]]})
    tid = ko.kor_ett({"id": "c", "max_min": 0, "kor": [[sys.executable, "-c", "print(1)"]]})
    assert ok["status"] == "klar" and fel["status"] == "fel" and "kod 3" in fel["fel"] and tid["status"] == "tidsgräns"


def test_dom_ur_analysens_tabell(tmp_path, monkeypatch):
    ko = _ko(tmp_path, monkeypatch)
    rad = {"varde": 0.5, "diff": 0.02, "lo": 0.01, "hi": 0.03}
    tab = {"tabell": {"kvart/alla": {"CSI 1": rad}}, "dagar": ["d1", "d2"],
           "dom": {"battre": True, "battre_i": ["kvart CSI 1"], "samre_i": []}}
    f = tmp_path / "t.json"
    f.write_text(json.dumps(tab))
    d = ko.doma({"domare": "analys", "fil": str(f)})
    assert d["battre"] and d["storsta_sakra_vinst"] == 0.01 and d["storsta_vinst_i"] == "kvart CSI 1" and d["dagar"] == 2


def test_mattat_spar(tmp_path, monkeypatch):
    ko = _ko(tmp_path, monkeypatch)
    rs = [{"id": f"{i}", "spar": "s", "slut": f"2026-11-{10 + i}", "dom": {"battre": True, "storsta_sakra_vinst": v}}
          for i, v in enumerate([0.01, 0.02, 0.03, 0.031, 0.031, 0.032])]
    assert ko.spar_lage(rs)["s"]["mattat"]
    rs[-1]["dom"]["storsta_sakra_vinst"] = 0.05
    assert not ko.spar_lage(rs)["s"]["mattat"]
