# Moving the engine to AWS for one week (zero cost)

The worker (the "engine": routing, the lab, the five agents, page checks, mockups) moves from this PC to one AWS
EC2 **t4g.small** for a week. Nothing else moves: the Studio stays on Vercel, jobs, logins and files stay on Supabase,
and the models stay on the same free APIs. The worker only makes outbound calls, so the server needs no domain and no
open ports except SSH from your own IP.

| | |
|---|---|
| Server | EC2 t4g.small (2 Graviton vCPU, 2 GB RAM, ARM), Ubuntu 24.04, 20 GiB gp3, 4 GB swap |
| On disk | the cream layer 2.4 GB, lab caches 68 MB, font index 8 MB, CLIP ViT-B-32 0.6 GB, Python + Chromium ~1.5 GB |
| Memory | engine ~1.1 GB loaded (1.6 GB peak at start) + Chromium 0.3-0.5 GB during checks/mockups; swap covers the rest |
| Layout | `/srv/cosmogon/{studio, lab, data, cache, tmp, venv, worker.env}`; keys in `studio/worker/.env` (mode 600) |

## Why it costs nothing (and the settings that keep it that way)

| Item | Normal price for 7 days | Why $0 |
|---|---|---|
| t4g.small, 168 h | ~$2.82 | AWS's t4g.small free trial: 750 h/month until 31 Dec 2026, every account |
| CPU above baseline | $0.04 / vCPU-h | **Credit specification: Standard** (the CPU slows down instead of billing) |
| 20 GiB gp3 | ~$0.37 | your Free Plan credits |
| Public IPv4 | ~$0.84 | your Free Plan credits |
| Data in / out | $0 | inbound is free; outbound under 100 GB/month is free |

Rules: no Elastic IP, no NAT gateway, no S3, no second instance, and **Terminate** (not Stop) at the end.

---

## 0. Account (once, ~10 min)
1. Billing and Cost Management → **Budgets** → Create → **Zero spend budget** → your email.
2. Billing → **Free Tier** / **Credits**: note the credit balance and the plan's end date (must be after the week).
3. MFA on the root user.
4. Choose **one region** near you and use it for everything below (top-right region picker).

## 1. Build and verify the bundle on this PC (done 2026-11-22; repeat after code changes)
```powershell
D:\caches\venvs\uifp\Scripts\python.exe D:\serpman-studio\deploy\pack.py            # -> D:\serpman_deploy\{code.tar.gz, data.tar, manifest.json}
D:\caches\venvs\uifp\Scripts\python.exe D:\serpman-studio\deploy\verify_bundle.py   # must end "BUNDLE OK: self-contained"
```
`verify_bundle.py` unpacks both archives in the server's layout, hides the original folders and runs the unpacked
engine (three jobs, browser checks) plus the offline test suite. It fails if the engine touches any file that is not
in the bundle. Before copying keys: add `OPENROUTER_API_KEY=...` to `D:\serpman-studio\worker\.env` if you have one
(without it A1 / A5 use Mistral, then Gemini).

## 2. Launch the server (EC2 console → Instances → **Launch instances**, ~10 min)
| Field | Value |
|---|---|
| Name | `cosmogon-engine` |
| AMI | **Ubuntu Server 24.04 LTS**, architecture **64-bit (Arm)** |
| Instance type | **t4g.small** |
| Key pair | Create new → name `cosmogon`, type ED25519, **.pem** → save as `D:\keys\cosmogon.pem` |
| Network | default VPC · **Auto-assign public IP: Enable** · Create security group · **Allow SSH from: My IP** (nothing else) |
| Storage | **20 GiB gp3** (Delete on termination stays on) |
| Advanced details → **Credit specification** | **Standard** |

Launch, wait for "2/2 checks passed", copy the **Public IPv4 address**. Do not allocate an Elastic IP.

Lock the key file once (OpenSSH refuses keys other users can read):
```powershell
icacls D:\keys\cosmogon.pem /inheritance:r /grant:r "$($env:USERNAME):(R)"
```

## 3. Upload (~20-90 min, depends on your upload speed)
```powershell
$IP = "<public-ip>"
scp -i D:\keys\cosmogon.pem D:\serpman_deploy\code.tar.gz D:\serpman_deploy\data.tar "ubuntu@${IP}:/tmp/"
scp -i D:\keys\cosmogon.pem D:\serpman-studio\worker\.env "ubuntu@${IP}:/tmp/worker.env"
```
The keys file goes straight from your disk to the server; it is never in the archives or in chat.

## 4. Install and check (~30 min, mostly unattended)
```bash
ssh -i D:\keys\cosmogon.pem ubuntu@<public-ip>
tar -xzf /tmp/code.tar.gz -C /tmp studio/deploy/bootstrap.sh
sudo bash /tmp/studio/deploy/bootstrap.sh
bash /srv/cosmogon/studio/deploy/check.sh
```
`bootstrap.sh`: 4 GB swap → unpack → keys (600) → Python 3.13 via uv + pinned packages (torch CPU-only) →
Chromium with its libraries → CLIP weights → the systemd service (installed, not started). Safe to re-run.
`check.sh`: `doctor --keys` (Supabase, bucket, Playwright, each key's models) → the offline test suite → one real
page end to end with peak memory. Your PC keeps serving the Studio while this runs.

## 5. Switch over (~5 min)
1. On the PC: Ctrl+C in the worker window (the Studio badge goes offline).
2. On the server:
   ```bash
   sudo systemctl enable --now cosmogon-worker
   journalctl -u cosmogon-worker -f        # "engine ready ...", then "worker ... polling"
   ```
3. The Studio badge reads **Engine online** within ~20 s. Generate one site from the Studio.

Two workers would not double-process a job (claims are atomic in Supabase), but keep only one running.

## 6. During the week
| Task | Command |
|---|---|
| Status | `systemctl status cosmogon-worker` · the Studio badge |
| Live log | `journalctl -u cosmogon-worker -f` |
| Memory | `free -h` · `journalctl -k \| grep -i oom` |
| Restart | `sudo systemctl restart cosmogon-worker` |
| Code update | PC: `pack.py --code-only` → `scp code.tar.gz` to `/tmp` → server: `sudo bash /srv/cosmogon/studio/deploy/update.sh` |
| Cost | Billing → Bills (daily: $0.00); the zero-spend budget emails on anything else |

- The service restarts the worker 10 s after any crash, and starts it at boot.
- If you Stop/Start the instance its public IP changes (only your `ssh`/`scp` address changes).
- Supabase's free project stays awake: the worker writes a heartbeat every 15 s.
- Each finished job logs `job <id>: took Ns (route .., a1 .., ...)`; those times keep the Studio's "about N min
  left" current (`studio/out/_agents/timing.json`, a moving average per step).

### Optional: your own GPU fallback on Modal (A1 / A5)
When every free model is busy, A1 / A5 can fall through to a model you run yourself on Modal (`modal_vlm.py`:
vLLM + Qwen3-VL-30B-A3B FP8 on one L40S, paid per second from Modal's $30/month Starter credit). Setup and costs are
in the file's header: `modal deploy deploy/modal_vlm.py`, then `MODAL_BASE` + `MODAL_API_KEY` in `worker/.env` (PC and
server) and a worker restart. With `MODAL_WARM=job` (default) the worker boots the GPU when a job starts and keeps it
up until the job ends (no cold start mid-job, ~10-15 GPU-minutes per job whether used or not); `MODAL_WARM=off` boots it
only on first use (2-4 min wait then).

## 7. Teardown (day 7, ~15 min)
1. Bring back what is worth keeping (PowerShell on the PC):
   ```powershell
   $IP = "<public-ip>"; mkdir D:\serpman_deploy\from-aws -Force
   scp -i D:\keys\cosmogon.pem -r "ubuntu@${IP}:/srv/cosmogon/studio/out/_agents" D:\serpman_deploy\from-aws\
   scp -i D:\keys\cosmogon.pem "ubuntu@${IP}:/srv/cosmogon/data/serpman_data/ui_drafts/p1/_context/_pi_cursor.json" D:\serpman_deploy\from-aws\
   ssh -i D:\keys\cosmogon.pem "ubuntu@${IP}" "journalctl -u cosmogon-worker --no-pager" > D:\serpman_deploy\from-aws\worker.log
   ```
   Optional: copy `_pi_cursor.json` over `D:\serpman_data\ui_drafts\p1\_context\_pi_cursor.json` so the PC continues
   the cloud's rotation instead of repeating picks.
2. EC2 → the instance → **Instance state → Terminate** (deletes the disk too).
3. Check nothing is left in the region: EC2 → Volumes (none), Snapshots (none), Elastic IPs (none). The key pair and
   security group are free; delete them if you like.
4. Restart the worker on the PC if it should keep serving.
5. Billing → Bills a day or two later: $0.00.

## Files here
| File | What |
|---|---|
| `pack.py` | builds the archives (contents measured with an audit hook over real jobs, not guessed) |
| `verify_bundle.py` | proves the archives are self-contained before uploading |
| `bootstrap.sh` | first-time server setup (idempotent) |
| `check.sh` | pre-switch checks on the server |
| `update.sh` | applies a new code archive, keeps server state |
| `cosmogon-worker.service` | systemd unit (restart always, clean SIGTERM exit) |
| `worker.linux.env` | Linux paths and thread limits (non-secret) |
| `requirements-linux.txt` | pinned packages from the PC's venv (torch installed separately, CPU wheels) |
| `datasums.py` | data.tar checksums + a small repair archive for damaged files (no 2.6 GB re-upload) |
| `modal_vlm.py` | optional: the A1 / A5 GPU fallback on Modal (see 6) |

## Code changes that make the move possible (no behaviour change on the PC)
- `worker/brief.py`: the cream root follows `SERPMAN_P1`; manifest paths are rebased when the data moved (`local_dest`).
- `worker/guardrails.py`: the font catalogue follows `SERPMAN_DATA`.
- `worker/worker.py`: SIGTERM takes the same clean exit as Ctrl+C (the badge goes offline at once).
- `worker/test_landing.py`: temp folder from `LANDING_TEST_TMP`; fixture paths rebased like the engine's.
- lab `route_engine.py`: `local_dest()` rebases a manifest's absolute `dest` onto this machine's cream root when the
  original path doesn't exist; on the PC every path exists, so routing is unchanged.
