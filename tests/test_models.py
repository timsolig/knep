"""Versionslåsningen av modellerna: pin, status och att fel kontrollsumma inte används."""

import json

from knep import models


def test_pin_and_versions(tmp_path):
    f = tmp_path / "extremes.pkl"
    f.write_bytes(b"modell")
    man = tmp_path / "models.json"
    man.write_text(json.dumps({"repo": "x/y", "models": {}}))
    models.pin("extremes", "extremes-v1", f, man)
    d = json.loads(man.read_text())
    assert d["models"]["extremes"]["sha256"] == models.sha256(f)
    assert models.versions(man) == {"extremes": "extremes-v1"}
    assert models.fetch(man) == 0  # filen finns redan med rätt summa, inget hämtas
