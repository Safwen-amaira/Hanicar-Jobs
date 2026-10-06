# Hanicar Jobs - Design System Master

**Product:** Hanicar Jobs  
**Tagline:** Don't search. Hunt.  
**Owner:** Safwen Amaira = Born as root  
**Generated for:** cybersecurity job / opportunity platform - dark gold premium  

This file is the single source of truth for visual and interaction decisions.

---

## Brand

| Token | Value | Usage |
|---|---|---|
| `--hj-bg` | `#0B0C0E` | OLED charcoal base |
| `--hj-bg-elevated` | `#14161A` | Panels, shells |
| `--hj-bg-muted` | `#1C1F26` | Subtle wells |
| `--hj-border` | `#2A2F3A` | Hairlines |
| `--hj-gold` | `#C9A227` | Single accent |
| `--hj-gold-soft` | `#E6C765` | Hover / focus glow (subtle) |
| `--hj-text` | `#E8EAED` | Primary text |
| `--hj-text-muted` | `#9AA0A6` | Secondary |
| `--hj-danger` | `#D64545` | Error / rejected |
| `--hj-success` | `#3DDC97` | Matched / success |
| `--hj-warn` | `#F0A500` | Deadline radar |
| `--hj-info` | `#5B8DEF` | Informational |

Status colors are reserved for states only - never decoration.

---

## Typography

| Role | Stack | Notes |
|---|---|---|
| UI | `"Sora", "IBM Plex Sans", sans-serif` | Refined sans |
| Data | `"IBM Plex Mono", "JetBrains Mono", monospace` | Scores, IDs, timestamps |
| Arabic / RTL | `"Noto Sans Arabic", "IBM Plex Sans Arabic", sans-serif` | Chosen early for RTL tuning |

---

## Motion

- Functional UI: 150–250 ms ease-out transitions; View Transitions between pages.
- Kanban: spring-physics drag.
- Cinematic (Three.js) only on: landing Hunt Map, SEARCH NOW sequence, optional match reveal.
- `prefers-reduced-motion`: static gradient poster, no WebGL, no parallax.
- Cap DPR at 1.5; pause when tab hidden / off-screen; dispose on unmount.
- Budget: ~250 kB gzip 3D chunk; 60 fps mid-range laptop.

---

## Layout

- Bento-grid dashboard for work surfaces.
- Command palette (Ctrl+K).
- Keyboard-first tables.
- Skeleton / empty / error states everywhere.
- Breakpoints gate: 375 / 768 / 1024 / 1440.
- Contrast AA+, visible focus rings (gold), no emoji decoration.

---

## Industry tone

Cybersecurity platform: precise, explainable, premium - HUD-adjacent without sci-fi noise. Gold is the hunt signal; charcoal is the field.

---

## Checklist (pre-delivery)

- [ ] Contrast AA+
- [ ] Focus states visible
- [ ] Reduced motion respected
- [ ] 375 / 768 / 1024 / 1440 checked
- [ ] Empty + error + loading states
- [ ] RTL flip for Arabic
- [ ] No purple gradient AI-default look
