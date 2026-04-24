# Digital Infrastructure Insider — Weekly Briefing

A weekly long-form editorial briefing on global digital infrastructure for senior investors and operators. Published in WSJ-article format; total read time ~45 minutes per edition.

---

## Repository structure

```
dii-briefing/
├── AGENT_PROMPT.md          ← Weekly agent run instructions (source of truth)
├── context/
│   ├── DIGEST.md            ← Stable editorial reference: standards, beats, market data
│   ├── THREADS.md           ← Live story threads, updated each run (~300 words)
│   └── nsr-src-*.txt        ← Deep reference source documents (load only when needed)
├── editions/
│   ├── ed6_2026-04-24.md    ← Full edition: 5–6 WSJ-style articles
│   └── ed6_2026-04-24.json  ← Edition manifest: titles, word counts, keywords
├── scripts/                 ← Archive: EP1–EP5 podcast scripts (historical)
└── shownotes/               ← Archive: EP1–EP5 show notes JSON (historical)
```

---

## Weekly edition format

Each edition contains **5–6 standalone articles** in WSJ narrative style, totalling ~11,000 words (~45 min read at 250 wpm).

| Slot | Beat | Target words |
|---|---|---|
| Lead | Biggest story of the week | 2,500 |
| European Telecom | Operators, consolidation, Nordics/UK/WE | 2,000 |
| Data Infrastructure | Hyperscalers, AI compute, data centres | 2,000 |
| Energy & Power | PPAs, nuclear, grid constraints | 1,800 |
| Capital & Deals | M&A, PE, IPOs, fundraising | 1,800 |
| Geopolitics | Sovereignty, US/China, SEA, Middle East | 1,500 |

Article format: declarative headline → one-sentence deck → dateline → news-first lead → nut graf → data-dense body with subheadings → forward look. Third person throughout.

---

## Running the weekly agent

The agent prompt is in `AGENT_PROMPT.md`. Each run:

1. Loads `context/DIGEST.md` + `context/THREADS.md` (not previous editions)
2. Runs 6–8 web searches across beats
3. Writes and saves articles one at a time (token-efficient)
4. Updates `THREADS.md` with new/resolved story threads
5. Publishes to the web app and triggers the email briefing
6. Commits `editions/` and `context/THREADS.md` to the repo

**Prompt caching:** `DIGEST.md` is stable week-to-week and designed to sit in the cached prefix. Only `THREADS.md` (small) changes each run.

---

## Coverage priorities

- **Data Infrastructure**: Hyperscaler capex, data centre construction, GPU supply, inference economics
- **European Telecom**: Nordics (TDC NET, Tele2, Telenor, Elisa), UK (BT/Openreach, altnets, Ofcom), Western Europe (Deutsche Telekom, Orange, Telecom Italia, Vodafone, Iliad)
- **Connectivity**: Subsea cable, terrestrial fibre, routing geopolitics
- **Energy**: PPAs, nuclear, grid constraints (telco + data centre)
- **Capital Markets**: PE/infra funds, M&A, public listings
- **Geopolitics**: US/China tech decoupling, data sovereignty, SEA, Middle East

---

## Web publication

Editions are published to: `https://agile-hope-production.up.railway.app`

Webhook endpoints (require `x-webhook-secret` header):
- `POST /webhook/publish` — publishes edition content
- `POST /webhook/send-email` — triggers subscriber email

---

## Archive

`scripts/` and `shownotes/` contain the original EP1–EP5 podcast episodes (MAYA/JAMES format, 2026-03-15 to 2026-04-11). These are retained for historical reference and are not part of the current production workflow.
