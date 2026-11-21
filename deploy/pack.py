"""pack.py - build the two archives that move the engine to a Linux server (AWS week). Run on this PC:

    D:\\caches\\venvs\\uifp\\Scripts\\python.exe D:\\serpman-studio\\deploy\\pack.py [--out D:\\serpman_deploy] [--code-only]

code.tar.gz (~10 MB)  studio/{worker, contracts, deploy}, studio/out/_agents (agent cache + today's quota ledger),
                      lab/ (the serpman lab: top-level *.py and its small catalogue files; never the ui_drafts junction)
data.tar   (~2.5 GB)  serpman_data/ui_drafts/p1/context-cream/**          (the cream layer the engine searches)
                      serpman_data/ui_drafts/p1/_context/<fam>/{emb,colors}.npz + type_template.json, the lab state files
                      serpman_data/ui_drafts/p1/aesthetic-families/<fam>/  (empty: the lab only lists the family names)
                      serpman_data/fonts/{catalog,meta}.json, index.npz, hub_*.npy   (the font index, not the font files)

What goes in was measured, not guessed: an audit hook recorded every file the worker opened over Engine() + six jobs
in six families (2026-11-22). Secrets never go in: worker/.env is copied to the server separately (deploy/README.md).
The CLIP weights are not packed either; the server downloads the same public checkpoint from Hugging Face.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import tarfile
import time
from pathlib import Path

STUDIO = Path(os.getenv("STUDIO_SRC", r"D:\serpman-studio"))
LAB = Path(os.getenv("SERPMAN_SRC", r"C:\Users\Keshav Sharma\Downloads\serpman"))
DATA = Path(os.getenv("SERPMAN_DATA", r"D:\serpman_data"))
P1 = DATA / "ui_drafts" / "p1"

CODE_DIRS = ["worker", "contracts", "deploy", "fixtures/landing"]   # fixtures: the offline test suite's lab runs
CODE_SKIP_NAMES = {".env", "__pycache__", ".pytest_cache", "node_modules"}
CODE_SKIP_SUFFIX = {".pyc", ".pyo", ".log"}
LAB_EXT = {".py", ".csv"}
LAB_FILES = {"taste_queries.txt", "taste_queries.full.txt"}     # catalogue inputs, small
CONTEXT_STATE = ["_font_usage.json", "_pi_cursor.json", "_pi_digits.txt"]
CONTEXT_OPTIONAL = ["_ai_cache.json"]                # only exists once the lab's optional AI comparers ran
CONTEXT_PER_FAMILY = ["emb.npz", "colors.npz", "type_template.json"]
FONT_FILES = ["catalog.json", "meta.json", "index.npz", "hub_crop.npy", "hub_spec.npy"]


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


LF_SUFFIX = {".sh", ".service", ".env"}           # run by bash / systemd on Linux: CRLF would break them


def add_tree(tar: tarfile.TarFile, src: Path, arc: str, stats: dict) -> None:
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in CODE_SKIP_NAMES]
        for f in files:
            p = Path(root) / f
            if f in CODE_SKIP_NAMES or p.suffix in CODE_SKIP_SUFFIX:
                continue
            name = f"{arc}/{p.relative_to(src).as_posix()}"
            if p.suffix in LF_SUFFIX:                   # git's autocrlf may have given them Windows line endings
                data = p.read_bytes().replace(b"\r\n", b"\n")
                info = tarfile.TarInfo(name)
                info.size, info.mtime, info.mode = len(data), int(p.stat().st_mtime), 0o755 if p.suffix == ".sh" else 0o644
                tar.addfile(info, io.BytesIO(data))
            else:
                tar.add(p, arcname=name, recursive=False)
            stats["files"] += 1
            stats["bytes"] += p.stat().st_size


def pack_code(out: Path) -> dict:
    path, stats = out / "code.tar.gz", {"files": 0, "bytes": 0}
    with tarfile.open(path, "w:gz", compresslevel=6) as tar:
        for d in CODE_DIRS:
            add_tree(tar, STUDIO / d, f"studio/{d}", stats)
        agents = STUDIO / "out" / "_agents"
        if agents.is_dir():
            add_tree(tar, agents, "studio/out/_agents", stats)
        for p in sorted(LAB.iterdir()):                 # top level only: ui_drafts is a junction to the whole corpus
            if p.is_file() and (p.suffix in LAB_EXT or p.name in LAB_FILES):
                tar.add(p, arcname=f"lab/{p.name}", recursive=False)
                stats["files"] += 1
                stats["bytes"] += p.stat().st_size
    return {"archive": path.name, **stats, "size": path.stat().st_size}


def pack_data(out: Path) -> dict:
    path, stats = out / "data.tar", {"files": 0, "bytes": 0}
    missing = []

    def add(p: Path) -> None:
        if not p.exists():
            missing.append(str(p))
            return
        tar.add(p, arcname="serpman_data/" + p.relative_to(DATA).as_posix(), recursive=False)
        stats["files"] += 1
        stats["bytes"] += p.stat().st_size

    with tarfile.open(path, "w") as tar:                # images are already compressed: plain tar
        cream = P1 / "context-cream"
        for root, dirs, files in os.walk(cream):
            dirs.sort()
            for f in sorted(files):
                add(Path(root) / f)
        ctx = P1 / "_context"
        for f in CONTEXT_STATE:
            add(ctx / f)
        for f in CONTEXT_OPTIONAL:
            if (ctx / f).exists():
                add(ctx / f)
        fams = sorted(p.name for p in (P1 / "aesthetic-families").iterdir() if p.is_dir() and not p.name.startswith("_"))
        for fam in fams:
            for f in CONTEXT_PER_FAMILY:
                if (ctx / fam / f).exists() or f != "type_template.json":
                    add(ctx / fam / f)
            info = tarfile.TarInfo(f"serpman_data/ui_drafts/p1/aesthetic-families/{fam}")
            info.type, info.mode, info.mtime = tarfile.DIRTYPE, 0o755, int(time.time())
            tar.addfile(info)                           # the lab lists family names here; no images needed
        for f in FONT_FILES:
            add(DATA / "fonts" / f)
    return {"archive": path.name, **stats, "size": path.stat().st_size, "families": len(fams), "missing": missing}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.getenv("DEPLOY_OUT", r"D:\serpman_deploy"))
    ap.add_argument("--code-only", action="store_true", help="rebuild code.tar.gz only (code updates during the week)")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    parts = [pack_code(out)]
    if not a.code_only:
        parts.append(pack_data(out))
    for p in parts:
        p["sha256"] = sha256(out / p["archive"])
        print(f"{p['archive']:<13} {p['files']:>6} files  {human(p['bytes']):>9} in  {human(p['size']):>9} out  "
              f"sha256 {p['sha256'][:16]}…")
        if p.get("missing"):
            print(f"  missing ({len(p['missing'])}):", *p["missing"][:10], sep="\n    ")
    (out / "manifest.json").write_text(json.dumps({"built": time.strftime("%Y-%m-%d %H:%M:%S"), "parts": parts},
                                                  indent=1), encoding="utf-8")
    print(f"done in {time.time() - t0:.0f}s -> {out}")
    return 1 if any(p.get("missing") for p in parts) else 0


if __name__ == "__main__":
    raise SystemExit(main())
