#!/usr/bin/env bash
# check.sh - verify the server before switching the Studio over (deploy/README.md, step 4). Run as the normal user.
#   1 doctor: keys present, Supabase tables + write grants, the bucket, Playwright, the live studio URL; models per key
#   2 the offline landing suite on this CPU architecture (fake models, no quota)
#   3 one real page end to end, local only (no Supabase): engine -> agents -> page -> mockup, with peak memory
# The PC's worker can keep serving while this runs; nothing here claims a Studio job.
set -uo pipefail
ROOT=/srv/cosmogon
set -a; . "$ROOT/worker.env"; set +a
PY="$ROOT/venv/bin/python"
cd "$ROOT/studio/worker"
fail=0
step() { printf '\n\033[1;36m== %s\033[0m\n' "$*"; }

step "1/3 doctor --keys"
"$PY" worker.py doctor --keys || fail=1

step "2/3 test_landing.py (offline)"
LANDING_TEST_TMP="$ROOT/tmp" "$PY" test_landing.py 2>&1 | grep -E "^FAIL|ALL PASS|FAILED" || fail=1

step "3/3 one page, end to end (uses 2-3 free model requests)"
/usr/bin/time -v "$PY" worker.py once --prompt "a retro 1976 analog synth and vinyl festival, warm and loud" \
  --out "$ROOT/tmp/check-page" 2> "$ROOT/tmp/check-time.txt" || fail=1
grep -E "Maximum resident set size|Elapsed \(wall clock\)" "$ROOT/tmp/check-time.txt" || true
ls -la "$ROOT/tmp/check-page" 2>/dev/null | head -12
free -h

if [ $fail -eq 0 ]; then
  printf '\n\033[1;32mall checks passed.\033[0m Switch over: stop the PC worker (Ctrl+C), then\n'
  echo "  sudo systemctl enable --now cosmogon-worker && journalctl -u cosmogon-worker -f"
else
  printf '\n\033[1;31ma check failed - see above; the PC worker is still the one serving.\033[0m\n'
fi
exit $fail
