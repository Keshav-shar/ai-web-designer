# serpman studio

One sentence in → a design recipe from the serpman lab → a static website written section by section by Qwen.

```
Browser ─► Vercel (web/)  ── user JWT, RLS ──►  Supabase  ◄── outbound only ──  PC worker (worker/)
           /api/generate: validate, split            jobs queue, job_events          claim → lab → brief →
           /studio: live timeline (Realtime)         private Storage: sites/<uid>/   images → Qwen × sections →
           /sites/[id]: sandboxed preview, zip       Auth (invite only)              validate → Tailwind → upload
```

**API, not MCP.** The app is the only client and the pipeline is fixed, so it is REST plus a queue. An MCP adapter
(`get_recipe`, `generate_site`) can wrap the same backend later for outside agents.

## Layout

| path | what |
|---|---|
| `contracts/design_brief.v1.json` | the recipe contract (JSON Schema). Python validates it fully; `web/lib/brief.ts` (zod) reads it |
| `contracts/split.v1.json`, `prompts/split.md` | prompt → {full_query, vibe_query, ...}; the same prompt and fallback in `worker/split.py` and `web/lib/split.ts` |
| `contracts/prompts/section.md` | the per-section agent prompt (hard rules that `worker/validate.py` enforces) |
| `contracts/catalog.json` | 39 vibes, 14 categories, section ids (from serpman's `taste_catalog`) |
| `worker/` | `worker.py` (once / run), `brief.py`, `guardrails.py`, `agent.py`, `validate.py`, `assemble.py`, `assets.py`, `qwen.py`, `supa.py` |
| `tools/export_tokens.py` | a lab run → the web app's theme (`web/app/theme/tokens.css`, `tokens.json`, `fonts.ts`) |
| `tools/export_catalog.py` | regenerates `contracts/catalog.json`, `web/lib/catalog.json`, `web/lib/split-prompt.generated.ts` |
| `supabase/migrations/` | tables, RLS, column grants, quota trigger, `claim_job()`, Realtime, private bucket |

## What the worker adds on top of the lab

- **Split.** The vibe query goes to the router and the full query goes to section planning. Mixing domain words into the vibe query pulled the dreamy app run toward dev-SaaS sections.
- **Taste at runtime.** `taste_affinity` gives the category's best niche for the routed vibe, a clash flag, and the vibes to avoid. All of these go into the prompts.
- **Guardrails** (`worker/guardrails.py`). Every change is logged in `brief.typography.overrides` with its reason:
  - WCAG repair along OKLab lightness: text 7:1, muted text 4.5:1, button label 4.5:1, button fill 3:1;
  - cue constraints on fonts ("soft italic serifs" means a serif face that has italics);
  - normal-width body text;
  - a display type scale (ratio of at least 1.25, body leading of at least 1.5);
  - **no baked-in text in page graphics:** more than 3 text lines, or a text box taller than 15% of the image, is replaced with the next clean lab candidate or dropped.
- **Images.** Only `background` and `central` images appear on a page. Layout and hero screenshots are structural references, shown only in the private recipe view.

## Setup

1. **Supabase**
   1. Create a project.
   2. Run `supabase/migrations/20261120000000_init.sql`, either in the SQL editor or with `npx supabase db push`.
   3. Under Auth, disable sign-ups and invite testers by email.
   4. Optionally enable GitHub OAuth.
   5. Add `https://<your-vercel-domain>/auth/callback` and `http://localhost:3000/auth/callback` to the redirect URLs.
2. **Web** (`web/`, npm cache on D: via `.npmrc`)
   1. Run `npm install`.
   2. Copy `.env.example` to `.env.local` and fill it in.
   3. Run `npm run dev`.
   4. On Vercel: set the root directory to `web`, and set the same env vars. The **service-role key is never set here**.
3. **Worker**, with `D:\caches\venvs\uifp\Scripts\python.exe` and env vars only, never files:
   - `QWEN_BASE`, `QWEN_API_KEY`, `QWEN_MODEL` (a coder-class model);
   - optional: `QWEN_SPLIT_MODEL`, `QWEN_VL_MODEL`;
   - `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`;
   - optional: `LAB_AI_KEY`, `LAB_AI_BASE`, `LAB_AI_MODEL`, so the lab's own AI comparers use Qwen too.

   Then:
   ```
   python worker\worker.py once --prompt "a natural wine bar in Lisbon, hand-drawn and loud"   # local, no Supabase
   python worker\worker.py run                                                              # serve the queue
   ```
   Tailwind compiles with `web/node_modules/.bin/tailwindcss` (run `npm install` once), or with `TAILWIND_BIN`.

## Re-skin the app from the lab

```
cd C:\Users\...\serpman
D:\caches\venvs\uifp\Scripts\python.exe route_engine.py query "dreamy ethereal ai website builder landing page" --lab --fam dreamy-ethereal --full > D:\serpman-studio\fixtures\lab_dreamy_full.json
cd D:\serpman-studio
D:\caches\venvs\uifp\Scripts\python.exe tools\export_tokens.py fixtures\lab_dreamy_full.json --theme light [--heading "Fraunces"]
```
The export refuses to write a theme that still fails contrast.

## Checks

- `python worker\test_validate.py`: the section checker (scripts, handlers, external URLs, literal colours, placeholders).
- `npm run check:brief -- ..\out\dew\brief.json`: a Python-made brief parses in the UI schema.
- `npm run typecheck`, `npm run build`
- `python tools\shoot.py <url-or-file> <prefix>`: desktop and phone screenshots, with a horizontal-overflow check.
