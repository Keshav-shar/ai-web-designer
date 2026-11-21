"""verify_bundle.py - prove the two archives are self-contained before uploading them. Run on this PC:

    D:\\caches\\venvs\\uifp\\Scripts\\python.exe D:\\serpman-studio\\deploy\\verify_bundle.py [--keep]

Unpacks code.tar.gz + data.tar into D:\\serpman_deploy\\verify (the server's /srv/cosmogon layout), points every path
variable there (as worker.linux.env does on the server), then runs the *unpacked* worker: Engine() and three jobs in
three families through the agent pipeline with models off and the browser checks on. An audit hook fails the run if
anything is read from the original corpus (D:\\serpman_data) or the original lab folder, i.e. if the bundle is missing
a file the engine needs. The CLIP weights come from this PC's Hugging Face cache (the server downloads them).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

DEPLOY = Path(os.getenv("DEPLOY_OUT", r"D:\serpman_deploy"))
V = DEPLOY / "verify"
REAL_DATA = os.path.normcase(os.getenv("REAL_SERPMAN_DATA", r"D:\serpman_data"))
REAL_LAB = os.path.normcase(os.getenv("REAL_SERPMAN_SRC", r"C:\Users\Keshav Sharma\Downloads\serpman"))
REAL_STUDIO = os.path.normcase(r"D:\serpman-studio")

# Simulate the server: the original folders don't exist there, so make them look absent here (exists() only).
HIDE = r'''
import os, pathlib
_real = [os.path.normcase(os.environ[k]) for k in ("REAL_DATA", "REAL_LAB", "REAL_STUDIO")]
def _hidden(p):
    p = os.path.normcase(os.path.abspath(os.fsdecode(p)))
    return any(p == r or p.startswith(r + os.sep) for r in _real)
_pe, _ope = pathlib.Path.exists, os.path.exists
pathlib.Path.exists = lambda self, *a, **k: False if _hidden(self) else _pe(self, *a, **k)
os.path.exists = lambda p: False if _hidden(p) else _ope(p)
'''
RUN = HIDE + r'''
import os, sys, json, time
from pathlib import Path
leaks = set()
real = [os.environ["REAL_DATA"], os.environ["REAL_LAB"], os.environ["REAL_STUDIO"]]
def hook(event, args):
    if event == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)):
        p = os.path.normcase(os.path.abspath(os.fsdecode(args[0])))
        if any(p.startswith(r + os.sep) for r in real):
            leaks.add(p)
sys.addaudithook(hook)
sys.path.insert(0, os.getcwd())
import worker as W
from split import fallback, sanitize
from landing import handoff as LH, pipeline as LP
t = time.time()
eng = W.Engine()
out = {"engine_s": round(time.time() - t), "jobs": []}
for p in ["a retro 1976 analog synth and vinyl festival", "minimal scandinavian furniture store",
          "dark fintech analytics dashboard"]:
    t = time.time()
    split = sanitize(fallback(p), p)
    o, brief, files = eng.recipe(p, split, None, "auto", serve=False)
    h = LH.build(o, split, brief, files, theme="auto", resolve=eng.resolve, text_lines=eng.text_lines)
    od = Path(os.environ["SERPMAN_TMP"]) / ("verify-" + brief["meta"]["routed_family"])
    r = LP.run(h, enabled=False, out_dir=od, qa=True, log=lambda *a: None)
    probs = [x for w in (r["qa"] or {}).values() for x in w["problems"]]
    out["jobs"].append({"prompt": p, "family": brief["meta"]["routed_family"], "page": r["page_source"],
                        "assets": len(list((od / "assets").glob("*"))), "qa_problems": len(probs),
                        "s": round(time.time() - t)})
out["leaks"] = sorted(leaks)[:20]
print("VERIFY " + json.dumps(out))
'''


def main() -> int:
    keep = "--keep" in sys.argv
    if V.exists():
        shutil.rmtree(V)
    (V / "data").mkdir(parents=True)
    with tarfile.open(DEPLOY / "code.tar.gz") as t:
        t.extractall(V, filter="data")
    with tarfile.open(DEPLOY / "data.tar") as t:
        t.extractall(V / "data", filter="data")
    for d in ("tmp", "studio/out/_agents", "studio/out/_landing"):
        (V / d).mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update({
        "SERPMAN_SRC": str(V / "lab"), "SERPMAN_DATA": str(V / "data" / "serpman_data"),
        "SERPMAN_P1": str(V / "data" / "serpman_data" / "ui_drafts" / "p1"), "SERPMAN_TMP": str(V / "tmp"),
        "HF_HOME": os.getenv("HF_HOME", r"D:\caches\huggingface"),
        "LANDING_ENV_FILE": str(V / "no-keys.env"), "LANDING_OUT": str(V / "studio" / "out" / "_landing"),
        "LANDING_CACHE": str(V / "studio" / "out" / "_agents" / "cache"),
        "LANDING_LEDGER": str(V / "studio" / "out" / "_agents" / "quota.json"),
        "LANDING_UNAVAIL": str(V / "studio" / "out" / "_agents" / "unavailable.json"),
        "REAL_DATA": REAL_DATA, "REAL_LAB": REAL_LAB, "REAL_STUDIO": REAL_STUDIO,
        "PYTHONIOENCODING": "utf-8", "SECTION_MODE": "agents"})
    for k in [k for k in env if k.endswith("_API_KEY") or k.endswith("_API_KEYS")]:
        env.pop(k)                                      # models off: nothing leaves the PC
    r = subprocess.run([sys.executable, "-c", RUN], cwd=V / "studio" / "worker", env=env, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    line = next((x for x in r.stdout.splitlines() if x.startswith("VERIFY ")), None)
    if not line:
        print(r.stdout[-3000:], r.stderr[-3000:], sep="\n")
        return 1
    res = json.loads(line[7:])
    print(json.dumps(res, indent=1))
    t = subprocess.run([sys.executable, "-c", HIDE + "import runpy, sys; sys.argv = ['test_landing.py']; "
                        "sys.path.insert(0, '.'); runpy.run_path('test_landing.py', run_name='__main__')"],
                       cwd=V / "studio" / "worker",
                       env={**env, "LANDING_TEST_TMP": str(V / "tmp")}, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    summary = [x for x in t.stdout.splitlines() if x.startswith(("FAIL", "ALL PASS")) or "FAILED" in x]
    print("bundled test_landing.py:", *summary[-6:], sep="\n  ")
    ok = not res["leaks"] and all(j["page"] in ("compile_spec", "model") and j["assets"] > 0 for j in res["jobs"]) \
        and any(x.startswith("ALL PASS") for x in summary)
    print("BUNDLE OK: self-contained" if ok else "BUNDLE PROBLEM: see above")
    if not keep:
        shutil.rmtree(V, ignore_errors=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
