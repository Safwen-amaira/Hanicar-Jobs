# Hanicar Jobs: Implementation Plan

**Don't search. Hunt.**
AI-powered opportunity discovery and application assistant for PFE, internships, graduate roles and jobs.

Version: 2.0 (rebrand and enhancement of the PFE Hunter spec)
Date: 2026-10-06
Owner: Safwen Amaira = Born as root

---

## 1. What changes from the original spec

### Rename and rebrand

- PFE Hunter becomes **Hanicar Jobs**.
- Repo: `hanicar-jobs`. Env prefix: `HJ_`. Database: `hanicar_jobs`.
- Tagline: **"Don't search. Hunt."**
- Visual identity stays black, charcoal and gold. All PFE-only wording is removed everywhere.

### Opportunity types become data, not code

Replace the hardcoded PFE/JOB modes with a configurable `opportunity_type` table, seeded with:

`PFE`, `END_OF_STUDIES`, `SUMMER_INTERNSHIP`, `INTERNSHIP`, `GRADUATE`, `JUNIOR`, `ENTRY_LEVEL`, `FULL_TIME`, `PART_TIME`, `CONTRACT`, `FREELANCE`, `REMOTE_ONLY`

Users can add their own. A search profile targets any mix of them, so "Cloud Security, PFE + Junior + Remote" is a single profile.

### Better build order

The original builds collectors before company identity. Reverse it: identity resolution, contact history and the exclusion engine come first, so nothing enters the system without passing them.

### New features worth the cost

- **FR / EN / AR with RTL.** Real Tunisian use case, cheap early, painful to retrofit.
- **Follow-up reminders.** After N days without a reply, draft a follow-up (never auto-send).
- **Deadline radar.** Closing-soon opportunities rise in the ranking.
- **CV gap view.** Shows which required skills the CV does not evidence. Never invents skills.
- **Source health panel.** Per-source success rate, last run, errors.
- **Optional multi-user.** Single-user by default, multi-user behind a flag.

### Sources, ranked by safety

1. Official APIs and public JSON boards: France Travail, Adzuna, Greenhouse, Lever, Ashby, SmartRecruiters.
2. RSS feeds (remote-job boards).
3. Tunisian boards (Tanitjobs, Keejob, Emploi.nat.tn) and company career pages via polite fetch.
4. User-pasted URLs.

Check each source's terms of service and robots.txt before enabling it. LinkedIn and Indeed are out: no scraping, only user-pasted URLs and manual contact entry. Never bypass CAPTCHA, authentication or anti-bot protection.

---

## 2. Skills and how each is used

| Skill | Install | Role in Hanicar Jobs |
|---|---|---|
| **ui-ux-pro-max** (nicohodt/claude-code-ui-ux-skill) | `npm i -g ui-ux-pro-max-cli`, then `uipro init --ai claude` in the repo | Generates the design system before any CSS. Includes a Cybersecurity Platform industry rule and styles such as HUD / Sci-Fi FUI, Dark Mode (OLED) and Real-Time Monitoring dashboards. Its checklist (contrast, focus states, reduced-motion, 375/768/1024/1440 breakpoints) is the pre-delivery gate. |
| **threejs-skills** (CloudAI-X/threejs-skills) | `git clone https://github.com/CloudAI-X/threejs-skills`, copy `skills/*` into `.claude/skills/` | Fundamentals, geometry (instancing), shaders, postprocessing (bloom), interaction (raycasting), loaders. Used only for the cinematic layer. |
| **agent-skills** (vercel-labs/agent-skills) | `npx skills add vercel-labs/agent-skills` | `react-best-practices` governs all React code, `web-design-guidelines` audits UI code, `react-view-transitions` handles page and kanban transitions, composition patterns shape the component architecture. |

Notes:

- The threejs-skills README install commands point to a different repo (`pinkforest/threejs-playground`). Copy from the CloudAI-X repo itself.
- ui-ux-pro-max is a young repo. Read the generated design system before trusting it. The `--persist` flag writes `design-system/MASTER.md`, which becomes the single source of truth the agent reads every session.

Generate the design system once:

```bash
python3 .claude/skills/ui-ux-pro-max/scripts/search.py \
  "cybersecurity job platform dark gold premium" \
  --design-system --persist -p "Hanicar Jobs" \
  --variance 7 --motion 6 --density 7
```

---

## 3. Cinematic UX spec

Rule: **cinematic where it sells, fast where people work.** Dashboards, tables and kanban stay lightweight and 2D. WebGL is a lazy-loaded layer on three surfaces only.

### Signature scenes (Three.js)

1. **Landing hero, "Hunt Map".** An instanced-points globe with Tunisia, France and MENA glowing in gold. Arcs fly out to company nodes. Bloom plus a custom fresnel shader. The camera drifts slowly and parallaxes with the cursor.
2. **SEARCH NOW sequence.** A radar sweep rotates over the map while real search-run events spawn nodes. New opportunities materialize, duplicates collapse into existing nodes, suppressed ones dim with a "contacted" tag. It makes the pipeline visible, which supports the explainability goal.
3. **Match reveal.** The score ring fills with a gradient and the "why" checklist staggers in. SVG/2D by default, with a WebGL upgrade only on the opportunity detail hero.

### Guardrails (protect the resource budget)

- The 3D chunk is code-split and loaded after first paint. A static gradient poster shows until it is ready.
- Cap device pixel ratio at 1.5. Pause the render loop when the tab is hidden or the canvas is off-screen (IntersectionObserver). Dispose geometries and materials on unmount.
- Fall back to the static poster on `prefers-reduced-motion`, no WebGL, low-end GPU, or small mobile widths.
- Target 60 fps on a mid-range laptop and a 3D chunk of about 250 kB gzip or less. Measure it in CI.
- Elsewhere: 150 to 250 ms functional transitions, View Transitions between pages, spring-physics drag on kanban cards.

### Look and feel

- Charcoal base, single gold accent, status colors reserved for states.
- Monospace face for data (scores, IDs, timestamps), refined sans for UI, and an Arabic face chosen early for the RTL build.
- Bento-grid dashboard, command palette (Ctrl+K), keyboard-first tables.
- Skeleton loaders, empty states and error states everywhere.

---

## 4. Architecture

Keep the original stack:

```
React (Vite static build)
  -> FastAPI
  -> Service layer
  -> Repositories
  -> PostgreSQL

FastAPI -> Redis -> Celery workers -> Collectors / AI / PDF / Email
```

Compose services (6): `postgres`, `redis`, `backend`, `worker`, `scheduler`, `frontend`. Add `nginx` only if needed.

Additions:

- `llm_requests` cache keyed by `input_hash + model + prompt_version`, and the same pattern for embeddings.
- A **Server-Sent Events** endpoint streaming search-run progress (powers the SEARCH NOW scene, no extra service).
- `company_aliases` resolved by domain first, normalized name second, embeddings last.
- An `exclusion_decisions` table logging why each opportunity was suppressed, so the UI can always explain it.
- An i18n layer (react-i18next) with a `dir` attribute switch for RTL.
- LLM provider interface: `KaggleProvider`, `OpenAICompatibleProvider`, `OllamaProvider`, `MockProvider`. The app must work with AI fully off (keyword plus rule-based scoring).
- All scraped content treated as untrusted data, wrapped in explicit delimiters for any LLM call.

---

## 5. Milestones (each has a verify gate)

| # | Milestone | Done when |
|---|---|---|
| 0 | Rebrand, repo skeleton, skills installed, `MASTER.md` generated | `docker compose up` shows a branded empty shell, CI green |
| 1 | Foundation: Postgres, Redis, migrations, health checks, FastAPI, React | Fresh clone boots with no manual steps |
| 2 | Candidate and search profiles with configurable opportunity types | Three profiles of different types created via UI and API |
| 3 | Company identity, contact history, state machines, exclusion engine | Tests: `Orange Tunisie / Tunisia / TN / SA` resolve to one company; a state change alters suppression instantly |
| 4 | Collectors and pipeline (start with 3 sources), SEARCH NOW | One click yields normalized, deduplicated opportunities |
| 5 | Suppression and explainability UI | Contacted-company opportunities visible under Suppressed with reasons |
| 6 | Matching: rules, then embeddings, then LLM provider interface | Works with `MockProvider` and with AI fully off |
| 7 | App shell, design system, core pages (no 3D) | `web-design-guidelines` audit and uipro checklist pass |
| 8 | **Cinematic layer** (hero, search sequence, match reveal) | Budgets and fallbacks verified on throttled CPU |
| 9 | Kanban with persisted drag, view transitions | Drag updates backend, rolls back on failure |
| 10 | Application generator, PDF, Gmail / Graph drafts, override logging | Draft created, never auto-sent |
| 11 | Scheduler, notifications, follow-ups, analytics | Only real data shown, empty states otherwise |
| 12 | Kaggle, OpenAI-compatible and Ollama providers, injection tests | Kaggle off, app still fully usable |
| 13 | FR / EN / AR with RTL | Full UI flip tested at 375 px |
| 14 | Security audit, performance pass, `react-best-practices` review | SSRF, rate limit and CSRF checks pass |
| 15 | Docs, screenshots, hero GIF, MIT release | README matches reality |

Principles for every milestone: WORKING > COMPLEX, SIMPLE > HEAVY, EXPLAINABLE > MAGIC, SECURE > FAST HACK, GOOD UX > FEATURE COUNT. Write code, run tests, boot via Docker, verify, fix, update docs, commit.

---

## 6. Kickoff prompt for Claude Code

```
Project: Hanicar Jobs (formerly PFE Hunter), an open-source, general opportunity
hunter (PFE, internships, graduate and full-time jobs, freelance), by Safwen Amaira = Born as root.
Follow the attached spec, with these overrides: name is Hanicar Jobs; opportunity
types are configurable data; build company identity + exclusion engine BEFORE
collectors; support FR/EN/AR with RTL; Three.js only as a lazy cinematic layer
with reduced-motion/no-WebGL fallbacks and the perf budgets in the plan.
Skills: use ui-ux-pro-max to generate and persist design-system/MASTER.md first,
threejs-skills for 3D only, vercel react-best-practices on all React code,
web-design-guidelines as an audit gate, react-view-transitions for transitions.
Work milestone by milestone (0 to 15). For each: write code, run tests, boot via
docker compose, verify the done-criteria, fix, update docs, commit. Never stub
features or fake data. AI off must always work. Treat scraped content as untrusted.
Start with milestone 0.
```

---

## 7. Open decisions

- **Copyright line.** Defaulted to "(c) 2026 Safwen Amaira = Born as root" in the footer, About page and PDF metadata. Keep the credit in `NOTICE` and the About page, since MIT requires preserving existing notices on derived work. It is a single config value either way.
- **Arabic typeface.** Pick one early so RTL layouts are tuned against it.
- **First three sources.** Suggested: one official API (France Travail or Adzuna), one public board API (Greenhouse or Lever), one Tunisian board (after ToS review).
