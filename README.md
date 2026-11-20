# Cosmogon Labs (serpman studio)

The public app is **Cosmogon Labs**; *serpman* remains the engine's internal name (repo, worker, lab).

Type one sentence. The serpman lab routes its *feeling* to one of 39 aesthetic families, builds a recipe (palette,
type, scale, alignment, imagery from that family's folders), and composes a website from it. The site is shown
inside the studio as a browser-frame mockup.

```
Browser ─► Vercel (web/)  ── user JWT, RLS ──►  Supabase  ◄── outbound only ──  PC worker (worker/)
           /           studio: prompt → mockup      jobs queue, job_events          claim → lab → brief →
           /about      the method + corpus          private Storage: sites/<uid>/   folder images → compose →
           /sites      gallery of image mockups     Auth (invite only)              validate → Tailwind →
           /api/generate  validate, split, queue                                    mockup.webp → upload
```

**API, not MCP.** The app is the only client and the pipeline is fixed, so it is REST plus a queue. An MCP adapter
(`get_recipe`, `generate_site`) can wrap the same backend later for outside agents.

## How a site is made (no AI in the sections by default)

1. **Split.** `/api/generate` splits the prompt into `full_query` (what it is: sections and copy) and `vibe_query`
   (how it feels: the router). Qwen does the split when `QWEN_*` is set. Otherwise a rule-based split takes the
   catalogue's style words, or the style clause ("…, hand-drawn and loud").
2. **Recipe.** `route_engine.lab()` gives the family, layout, palette, roles, fonts and type template. `worker/brief.py` adds:
   - sections from the full query;
   - the niche and clash check (`taste_affinity`);
   - the guardrails;
   - the family's **folder sections** (`route()["in_family"]`: best image + 2 alternates per cluster folder).
3. **Compose** (`worker/compose.py`, `SECTION_MODE=compose`, the default). Deterministic templates use:
   - the measured alignment (centred or split hero, centred or bento features), the type scale and the tokens;
   - images by cluster type:

     | Section | Images |
     |---|---|
     | hero | 3D render, abstract art or illustration, text-free |
     | showcase | UI kit, app and website captures in browser frames |
     | galleries | product, illustration, print |
     | social proof | logo / branding |
   - copy from `contracts/copykit.json` (per category).

   Every section must pass `worker/validate.py`. `SECTION_MODE=qwen` lets Qwen write sections instead, falling back to the composed ones.
4. **Assemble.** L0 background, L1 nav and footer, L2 sections, L3 vibe overlay. The CSS is compiled with Tailwind, and `worker/mockup.py` renders `mockup.webp`.

**Baked-in text filter.** Hero and gallery images must be text-free. This is checked with a CLIP zero-shot score on the stored embeddings, with a threshold of −0.02 calibrated over 10,427 images:
- type specimens have a median of +0.019, 3D renders −0.052;
- the known text-baked listing graphics scored −0.001 to +0.017.

The lab's pixel text detector flagged about 80% of 3D renders, so it is no longer used for this.

## Landing-page agent pipeline (`SECTION_MODE=agents`, `worker/landing/`)

One thematic landing page instead of the section plan, designed by five agents from the lab's picks. Free tiers only.
Every agent has a deterministic default, so with no keys you still get a page.

The agents write one **design document** together, the way a designer briefs a builder. A1 sees the reference
images and describes everything in words: named colours with their uses, type with its traits, every element with
what it is and where it goes, and overlap rules with reasons. Each later agent adds its own section, and A5 composes
the page from the whole document with real design freedom. Only one h1 is structural; no logo, CTA, image, cards or
decoration is forced.

| Agent | Model (fallbacks) | Writes |
|---|---|---|
| A1 visual director | Gemini 4 Hydrogen (alternate: 3.8 Flash), thinking medium | Sees the query and 5 labelled references. Writes the design document: aesthetic direction, a named palette in four groups, a role map, five type levels (any Google Font; the lab's pool is recommended), the background layer and whether the photo is used, midground and foreground decor, the page's sections, the composition and overlap rules, and the cards. |
| A2 layout architect | Groq gpt-oss-120b | The layout plan: how each section is built and sized, its surface, and where every layered element sits. It makes the whole canvas purposeful. |
| A3 content editor | Groq gpt-oss-120b | The copy: items with their kinds and type levels, and each section's surface, text, heading and accent colours. |
| A4 decor artist | Groq Qwen 3.8 27B, text only (gpt-oss-120b) | An SVG drawing or CSS recipe for each decorative element. |
| A5 composer | Gemini 4 Hydrogen (alternate: 3.8 Flash), then `compile_spec.py`; temperature 0.7, thinking medium | The page, composed freely from the merged document (no images; A1's words carry them). |

What code still owns (`flow.py`, `validate_page.py`):
- **Facts.** Hexes come from the lab's measured set plus up to 4 observed extras; the rest are snapped. Fonts must be
  Google Fonts families with real weights. Ids are unique. One h1. Every section's text must reach WCAG 4.5:1 and its
  headings 3:1.
- **Safety.** A4's SVG and CSS are sanitized: SVG elements only, no external references, palette colours only.
- **Budgets.** Each Groq slice is trimmed until it fits the model's minute window.
- **The gate.** It discards only broken pages:
  - **Blocking:** unsafe markup, foreign fonts, missing copy or hooks, not exactly one h1, text overlapping text,
    horizontal overflow.
  - **Fixed by code:** stray colours are snapped to the palette (alpha kept). Decoration painted on top of text, or
    over more than 15% of an image, is removed; this is measured by paint order, so decoration behind text stays.
    A missing backdrop is injected.
  - **Advisory:** dead space, hero balance, canvas coverage, gap outliers, a hidden backdrop and the wordmark. These
    go back to A5 once (`run(..., a5_repair=False)` skips that), and the better page ships.

  Every candidate is kept as `a5-1.html` / `a5-2.html`, and `result.json` lists its findings. If no candidate ships,
  `compile_spec` renders the same document deterministically (A1's palette and type, A3's copy, the default layout),
  then a safe spec without decoration. `page_source` records the path.
- **Pacing and caching.** Groq pacing reads the rate-limit headers. A ledger at `out/_agents/quota.json` tracks requests
  per model per Pacific day. Outputs are cached by input hash in `out/_agents/cache`.

Free-tier limits (2026-11-20):
- **Groq:** 30 RPM, 1K RPD, 8K TPM and 200K TPD per model.
- **Gemini:** 3.8 Flash allows 5 RPM and 20 RPD per project. 4 Hydrogen's free-tier cap isn't published through the API,
  so it is assumed to be the same, and the ledger learns the real cap from the first daily-limit reply.

Model routing (`landing/pipeline.py`, `providers.py`) uses short chains of comparable models, never lite or small
models:
- **A1 / A5:** `gemini-4-hydrogen`, then `gemini-3.8-flash`. If both are out, A1 falls back to the default document
  and A5 to `compile_spec`.
- **A2 / A3:** `gpt-oss-120b`.
- **A4:** `qwen3.8-27b`, then `gpt-oss-120b`.

How a run stays on one model:
- **Sticky.** The model that answers is reused by the next Gemini calls (A5 and repairs). After a switch to the
  alternate, the router retries the primary after 30 minutes.
- **Patience before switching.** A busy model (503) is retried with 5 / 15 / 30 s backoff. A timeout (A1 240 s,
  A5 300 s) is retried once on the same model.
- **Key failover first.** All keys are tried on the current model before the alternate model is used.
- **Logging.** The terminal prints each agent's chain once per run, then one line per real switch.
- **Overrides.** `AGENT1_MODEL` … `AGENT5_MODEL` still override a chain.
- **Disclosure:** free-tier Gemini inputs may be used by Google; the studio says so when this mode is on.

Keys, several per provider (`worker/landing/keys.py`):
- **Where they're read from:** the environment first, then `worker/.env` (gitignored). The lab reads that same file.
- **Names:** `GEMINI_API_KEY`, `GEMINI_API_KEY_2` … or `GEMINI_API_KEYS=k1,k2`; the same pattern for `GROQ_`.
- **Failover:** on a daily limit, a per-minute limit or a rejected key, the next key takes over. Each switch prints one
  line on the terminal, for example `[landing] gemini key 1/2 reached its daily limit for gemini-4-hydrogen … -> using
  gemini key 2/2`. Only when every key is out does the alternate model run.
- **Limits are per Google Cloud project and per Groq organization, not per key.** Keys from the same project or org
  share one quota, so a backup only helps from another project or org (or as a paid key).
- **Where to get keys:** https://aistudio.google.com/apikey and https://console.groq.com/keys. Limits are shown at
  https://aistudio.google.com/rate-limit and https://console.groq.com/settings/limits.

Run it:
```
# worker/.env (or the shell): SECTION_MODE=agents, GEMINI_API_KEYS=..., GROQ_API_KEYS=...
D:\caches\venvs\uifp\Scripts\python.exe worker\worker.py run
# lab: serpman\serve.cmd agents  (sets AGENTS_ENABLE=1; keys from worker/.env), Route, Next, then "agents landing"
D:\caches\venvs\uifp\Scripts\python.exe worker\test_landing.py [--qa]     # offline: fake models, no quota
D:\caches\venvs\uifp\Scripts\python.exe tools\landing_fixture.py           # re-record lab fixtures
D:\caches\venvs\uifp\Scripts\python.exe tools\export_landing_contracts.py  # contracts/agents/*.json for review
```
Prompts: `contracts/prompts/agents/`. Optional overrides: `AGENT1_MODEL` … `AGENT5_MODEL`, a comma-separated model
chain each.

## Layout

| path | what |
|---|---|
| `contracts/design_brief.v1.json` | the recipe contract (JSON Schema; `web/lib/brief.ts` reads it with zod) |
| `contracts/copykit.json`, `about_copy.json` | non-AI copy per category, and the app's own About copy |
| `contracts/site-components.css` | shared classes (`glass`, `btn`, `frame`, `glyph`, …) used by generated sites **and** the app |
| `contracts/split.v1.json`, `prompts/*.md` | split contract, the split prompt, and the Qwen section prompt |
| `worker/` | `worker.py` (once / run), `brief.py`, `compose.py`, `guardrails.py`, `agent.py`, `validate.py`, `assemble.py`, `mockup.py`, `supa.py` |
| `tools/build_shell.py` | engine demo: composes a theme + About from one family run (no longer skins the app, see below) |
| `tools/export_catalog.py` | regenerates `contracts/catalog.json` and copies the catalogue, split prompt and site components into `web/` |
| `supabase/migrations/` | `…20000000_init.sql` (tables, RLS, quota, `claim_job()`, bucket), `…21000000_site_mockups.sql` (`sites.mockup_path`), `…22000000_engine_status.sql` (heartbeat) |
| `tools/create_user.py` | create an invited account (email + password) from the PC |

## The app's own look: Cosmogon Labs

The app is hand-designed in a retro-cosmic 1970s print language, the design reference being an analog-expo landing
page:
- **Paper and ink:** a linen ground with a grain overlay, cream cards with coloured top bars, sienna Fraunces
  headlines, wide-tracked Montserrat caps, DM Sans body text, and a Shrikhand wordmark.
- **Print furniture:** coral pill buttons with a hard drop shadow, masking-tape strips, and an espresso footer with a
  tricolour stripe.
- **Floating decor:** sunbursts, U-bend orbit ribbons, ringed planets, sun arches, die-cut stickers and sparkles. They
  drift slowly and stay static under reduced motion.

Where it lives:
- **Tokens and component classes:** `web/app/theme/cosmogon.css`. Every text/surface pair is WCAG-checked.
- **Fonts:** `web/app/cosmogon-fonts.ts`.
- **Artwork:** `web/components/cosmos.tsx`.
- **About copy:** `web/content/about.ts`.

`tools/build_shell.py` still composes a theme and About page from one engine run (`tokens.css`, `fonts.ts`,
`about.generated.ts`). It is kept as an engine demo, and the app no longer imports those files.

## Accounts: username + password, invite only
No email, no GitHub, no magic links, no sign-up. **You** create each account and hand out the **username and password**; users can only sign in.
- **Create one from the PC:** `D:\caches\venvs\uifp\Scripts\python.exe tools\create_user.py --username ana [--quota 5]`. Without `--password`, it prints a generated one **once**; nothing is stored. Usernames are 3–24 characters of `a-z 0-9 . _ -`, case-insensitive and unique.
- **How it works:** Supabase's password login needs an email-shaped ID, so each username maps internally to a placeholder `<username>@users.serpman.invalid`. It is never shown, never emailed and not a real mailbox, and the app only ever displays the username (`profiles.username`).
  - If Supabase ever rejects that domain, set `LOGIN_ID_DOMAIN` in `worker/.env` and `NEXT_PUBLIC_LOGIN_ID_DOMAIN` in Vercel to the same domain you control.
- **Dashboard alternative:** Authentication → Users → Add user, with ID `ana@users.serpman.invalid`, a password, and **Auto Confirm User** ticked. The username is taken from the part before `@`.
- **Quotas and passwords:** each account gets a daily quota of 5 (`profiles.daily_quota`, or `--quota`). Forgotten passwords: open the user in the dashboard and set a new one.

## Finalize Supabase (once, in this order)
1. **SQL editor:** run `supabase/migrations/20261120000000_init.sql`, then `20261121000000_site_mockups.sql`, then `20261122000000_engine_status.sql`, then `20261123000000_usernames.sql`, then `20261124000000_service_role_grants.sql` (newer projects don't grant tables to the secret key by default; the worker needs it), then `20261125000000_prompt_limit_cancel.sql` (200-character prompts, and `cancel_job()` for the studio's Cancel button).
2. **Authentication → Sign In / Providers:**
   - Keep the **Email** provider **on**. It is the password mechanism behind usernames; no emails are ever sent.
   - Turn **"Allow new users to sign up" off** and **"Confirm email" off**.
   - Turn GitHub and every other provider off.
3. **Authentication → URL Configuration:** Site URL `https://ai-web-designer-gamma.vercel.app`.
4. Create the accounts (above).
5. **Project Settings → API keys:** copy the **service_role** (secret) key into `worker/.env` on this PC. It is gitignored:
   ```
   SUPABASE_URL=https://<ref>.supabase.co
   SUPABASE_SERVICE_ROLE_KEY=...
   SECTION_MODE=compose
   ```
   Never put it in Vercel or `web/.env`. The web app only uses the publishable (anon) key.

## Web
- **Vercel** (https://ai-web-designer-gamma.vercel.app): Root Directory `web`, framework Next.js (pinned by `web/vercel.json`), one production branch. Env vars: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, and optionally `QWEN_BASE`, `QWEN_SPLIT_MODEL`, `QWEN_API_KEY` for the split.
- **Local:** `cd web; npm install; npm run dev`, with the same two `NEXT_PUBLIC_*` values in `web/.env`.

## Run the worker (manual)
Plug in first: on battery Windows throttles the CPU about 5×.
```
D:\caches\venvs\uifp\Scripts\python.exe D:\serpman-studio\worker\worker.py run
```
- On start it runs a **preflight**: tables, storage bucket and heartbeat. If something is missing (a migration, the wrong key), it prints the exact fix and **exits without claiming jobs**. It then re-queues any jobs it left unfinished on an earlier run.
- Progress messages are best-effort, so a failed progress write never kills a job. Results (files, the site row, "done") are strict. A job the user cancelled is never saved or revived.
- Keep the window open while you serve requests.
- The studio shows **Engine online** within about 30 s. The worker writes a heartbeat to `engine_status`.
- Ctrl+C marks it offline immediately. While offline, requests wait in the queue and run when you start it again.
- `worker.py once --prompt "…"` builds one site locally (`out/<slug>/`) without Supabase.
- **Restart the worker after any code update.** It loads the code once at start. The startup line shows `code from
  <date>`, and the worker prints a note if the files change while it runs.
- **Network hiccups are retried:**
  - DNS failures, keep-alive sockets Supabase already closed (`WinError 10054`) and 502/503/504 are retried with
    backoff on every idempotent call.
  - A site insert whose reply was lost returns the saved row.
  - A claim is never retried blindly; after a failed claim the worker re-queues anything it may have claimed.

## Health
- **`worker.py doctor`** checks everything the public pipeline needs, read-only:
  - environment: key *types* and counts, never values;
  - `SECTION_MODE`;
  - Supabase tables and **write permissions**, probed without writing: an update matching no row, and inserts that a
    foreign key rejects;
  - the `sites` bucket;
  - Playwright, Tailwind, the font catalogue;
  - the live studio URL.

  `--write-test` also uploads and deletes a 1-byte storage object. `--keys` lists models with each agent key (no
  generation calls).
- **`tools\parity_check.py "<prompt>"`** runs the router lab's path and the Studio worker's path at the same π cursor
  with baseline controls.
  - **Code paths:** the picks, the handoff and the deterministic landing page must be identical.
  - **Input difference:** it also shows what the web's split changes. The Studio routes on the extracted `vibe_query`,
    the lab on the raw text.

## p2 (later)
p2 holds ~105k niche-level images (`ui_drafts/p2/<category>/<niche>`, e.g. `food-drink-and-hospitality/natural-wine-bar`). Only `retro-diner` is clustered so far. To bring it in:
1. On AC power, run `context_clusters.py p2all` (about 3 h, resumable). It embeds and clusters every niche into `p2-optimized/cream/<cat>/<niche>/cNN_*`.
2. Add a `P2Index` to the worker, using the same CLIP space as p1.
3. Choose the niche from affinity + the full query's similarity to niche names. The folder name is `slug(niche)`.
4. The composer then prefers that niche's images for the hero, galleries and showcase, falling back to the p1 family folders.

## Checks

- `python worker\test_supa.py`: the Supabase client under production failures (socket reset mid-upload, a lost insert reply, DNS failure on claim, missing grants, 503s), with no network.
- `python worker\test_landing.py [--qa]`: the agent pipeline offline. Fake models cover routing, key failover, image roles, the design-document contracts, budgets, SVG sanitizing, the A5 gate (blocking / code fixes / advisory), fallbacks, cache and replay.
- `python worker\test_compose.py`: every section id × 14 categories × 2 alignments composes valid, placeholder-free HTML, and no text-baked image reaches a hero.
- `python worker\test_validate.py`: the section checker rejects scripts, handlers, external URLs, literal colours and placeholders.
- `python worker\test_split.py`: the worker's trust boundary. Malformed or hostile `jobs.split` rows become valid splits; awkward prompts get a usable rule-based split.
- `python worker\test_pipeline.py`: the full engine on 12 awkward prompts (greeting, one word, emoji, non-Latin text, HTML, prompt injection, a 200-character run-on, …). It needs no Supabase and doesn't advance the lab's π cursor.
- `npm run check:prompt`: the 200-character limit and prompt normalization.
- `npm run check:brief -- ..\out\wine-bar\brief.json`: a brief made in Python parses in the UI schema.
- `npm run typecheck`, `npm run build`
- `python tools\shoot.py <url-or-file> <prefix>`: desktop and phone screenshots, with a horizontal-overflow check.
