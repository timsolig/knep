"""Versioner av de tränade modellerna, lagrade som tillgångar i GitHub Releases.

Modellfilerna checkas inte in i git. I stället låser `models/models.json` vilken version som
gäller: en tagg, ett filnamn och en sha256 per modell. Taggen pekar på en release i repot, där
filen ligger som tillgång och release-texten beskriver träningen och verifieringen. Repot är
publikt, så hämtningen behöver ingen token.

    knep-models fetch                 hämta de låsta versionerna till models/ och kontrollera dem
    knep-models pin extremes extremes-v2 models/extremes.pkl
                                         lås en ny version (efter att releasen är skapad)
    knep-models status                vilka versioner som är låsta och om filerna stämmer

En ny version skapas med deploy/release_model.sh, som laddar upp filen med gh och låser den.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

MANIFEST = Path("models/models.json")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load(manifest: Path = MANIFEST) -> dict:
    return json.loads(manifest.read_text()) if manifest.exists() else {"repo": "", "models": {}}


def versions(manifest: Path = MANIFEST) -> dict:
    """Taggarna som är låsta, för manifestet på sidan: {"extremes": "extremes-v1", ...}."""
    return {k: v["tag"] for k, v in load(manifest).get("models", {}).items()}


def _repo(m: dict) -> str:
    repo = os.environ.get("GITHUB_REPO") or m.get("repo")
    if not repo:
        raise SystemExit("ange repot i models/models.json (\"repo\": \"ägare/knep\") eller GITHUB_REPO")
    return repo


def fetch(manifest: Path = MANIFEST) -> int:
    import requests

    m = load(manifest)
    bad = 0
    for name, e in m.get("models", {}).items():
        dst = manifest.parent / e["file"]
        if dst.exists() and sha256(dst) == e["sha256"]:
            print(f"{name}: {e['tag']} finns redan")
            continue
        url = f"https://github.com/{_repo(m)}/releases/download/{e['tag']}/{e['file']}"
        r = requests.get(url, timeout=120)
        if r.status_code != 200:
            print(f"{name}: kunde inte hämta {url} ({r.status_code})", file=sys.stderr)
            bad += 1
            continue
        tmp = dst.with_suffix(dst.suffix + ".part")
        tmp.write_bytes(r.content)
        if sha256(tmp) != e["sha256"]:
            tmp.unlink()
            print(f"{name}: fel kontrollsumma för {e['tag']}, filen används inte", file=sys.stderr)
            bad += 1
            continue
        tmp.replace(dst)
        print(f"{name}: hämtade {e['tag']}")
    return 1 if bad else 0


def pin(name: str, tag: str, path: Path, manifest: Path = MANIFEST) -> None:
    m = load(manifest)
    m.setdefault("models", {})[name] = {"tag": tag, "file": path.name, "sha256": sha256(path)}
    manifest.write_text(json.dumps(m, indent=1, ensure_ascii=False) + "\n")
    print(f"{name}: låst till {tag}")


def status(manifest: Path = MANIFEST) -> int:
    m = load(manifest)
    for name, e in m.get("models", {}).items():
        dst = manifest.parent / e["file"]
        state = "saknas" if not dst.exists() else "stämmer" if sha256(dst) == e["sha256"] else "skiljer sig från den låsta"
        print(f"{name:10s} {e['tag']:16s} {e['file']:16s} {state}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="knep-models", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--manifest", type=Path, default=MANIFEST)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch")
    sub.add_parser("status")
    q = sub.add_parser("pin")
    q.add_argument("name")
    q.add_argument("tag")
    q.add_argument("file", type=Path)
    a = p.parse_args(argv)
    if a.cmd == "fetch":
        return fetch(a.manifest)
    if a.cmd == "pin":
        pin(a.name, a.tag, a.file, a.manifest)
        return 0
    return status(a.manifest)


if __name__ == "__main__":
    raise SystemExit(main())
