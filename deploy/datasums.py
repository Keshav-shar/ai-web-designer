"""datasums.py - checksums for the data bundle, and small repair archives. Run on this PC:

    python datasums.py sums                 # data.tar -> data.sha1 (sha1sum format, paths relative to /srv/cosmogon/data)
    python datasums.py repair <list.txt>    # the paths in list.txt (one per line) -> repair.tar, taken from data.tar

On the server: `cd /srv/cosmogon/data && sha1sum -c --quiet /tmp/data.sha1` prints only missing or damaged files.
Uploading repair.tar for just those beats re-uploading 2.6 GB after a damaged or interrupted transfer.
"""
from __future__ import annotations

import hashlib
import os
import sys
import tarfile
from pathlib import Path

DEPLOY = Path(os.getenv("DEPLOY_OUT", r"D:\serpman_deploy"))


def sums() -> int:
    n = 0
    with tarfile.open(DEPLOY / "data.tar") as t, (DEPLOY / "data.sha1").open("w", encoding="utf-8", newline="\n") as out:
        for m in t:
            if not m.isfile():
                continue
            h = hashlib.sha1()
            f = t.extractfile(m)
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
            out.write(f"{h.hexdigest()}  {m.name}\n")
            n += 1
    print(f"{n} files -> {DEPLOY / 'data.sha1'}")
    return 0


def repair(listfile: str) -> int:
    want = {line.strip() for line in Path(listfile).read_text(encoding="utf-8").splitlines() if line.strip()}
    got = 0
    with tarfile.open(DEPLOY / "data.tar") as t, tarfile.open(DEPLOY / "repair.tar", "w") as out:
        for m in t:
            if m.name in want:
                out.addfile(m, t.extractfile(m) if m.isfile() else None)
                got += 1
    print(f"{got}/{len(want)} paths -> {DEPLOY / 'repair.tar'}")
    return 0 if got == len(want) else 1


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    raise SystemExit(sums() if cmd == "sums" else repair(sys.argv[2]) if cmd == "repair" else print(__doc__) or 2)
