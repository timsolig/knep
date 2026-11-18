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


def test_get_forsoker_igen_vid_504():
    """GitHub svarar ibland 504 eller 503 för release-filerna; hämtningen försöker igen."""

    class Svar:
        def __init__(self, kod):
            self.status_code = kod

    class Req:
        RequestException = OSError

        def __init__(self, koder):
            self.koder = list(koder)

        def get(self, url, timeout=None):
            k = self.koder.pop(0)
            if k is None:
                raise OSError("inget svar")
            return Svar(k)

    sov = []
    assert models._get(Req([504, None, 503, 200]), "u", sleep=sov.append).status_code == 200
    assert sov == [5.0, 10.0, 20.0]
    assert models._get(Req([404]), "u", sleep=sov.append).status_code == 404  # 404 görs inte om
    assert models._get(Req([504] * 3), "u", tries=3, sleep=lambda s: None).status_code == 504
