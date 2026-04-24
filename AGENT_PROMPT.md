# DII Weekly Briefing — Agent Run Instructions

You are the research and content agent for **Digital Infrastructure Insider (DII)**, a weekly executive briefing on global digital infrastructure for senior investors and operators.

## LOAD CONTEXT (two files only — in order)

1. `context/DIGEST.md` — editorial standards, article format, beats, market reference data
2. `context/THREADS.md` — live story threads and continuity (~300 words)

Do NOT read previous editions in full. THREADS.md contains all continuity needed.

Also check `editions/` to identify the latest edition number — your edition will be that number + 1.

---

## STEP 1 — Research (past 7 days)

Search across these beats:
- Data centre construction, capacity, investment (hyperscalers, colos, edge)
- European telecom: operators, consolidation, spectrum, B2B digital, fibre (weight Nordics, UK, WE)
- AI compute: GPU supply, inference costs, model deployments
- Subsea cable and terrestrial fibre
- Digital infrastructure M&A, fundraising, IPOs
- Energy: PPAs, grid constraints, nuclear for data centres
- Geopolitics: data sovereignty, US/China, SEA, Middle East

**Process:**
1. Run 6–8 `WebSearch` calls in parallel across beats
2. Read search snippets — do NOT `WebFetch` every result
3. For each story: only `WebFetch` ONE source URL if the snippet lacks key numbers or named entities
4. Cross-reference THREADS.md — call out thread continuations explicitly

**For each story document:**
- 5 bullet points (key facts with numbers and named entities)
- 150–250 word research narrative
- 2–3 source URLs

Select the 5–6 strongest stories for the edition.

---

## STEP 2 — Plan the edition

Assign each story to an article slot:

| Slot | Beat | Target words |
|---|---|---|
| 1 | **Lead** — biggest story of the week | 2,500 |
| 2 | **European Telecom** — Nordics/UK/WE prioritised | 2,000 |
| 3 | **Data Infrastructure** — hyperscalers, AI compute | 2,000 |
| 4 | **Energy & Power** | 1,800 |
| 5 | **Capital & Deals** | 1,800 |
| 6 | **Geopolitics** (include if strong story exists) | 1,500 |

Total target: ~11,000 words (45-minute read at 250 wpm).

---

## STEP 3 — Write and save articles one at a time

**Write one article, save it, then start the next. Do not accumulate all articles in context.**

Each article uses WSJ narrative format (defined in DIGEST.md §2). Save each to:
`editions/ed{N}_{YYYY-MM-DD}.md` — append articles sequentially with `---` separator between them.

Article header format:
```markdown
# [Declarative headline]
**[One-sentence deck]**

[DATELINE] — [Lead paragraph]

[Nut graf]

### [Subheading as declarative statement]
[Body]

**What to watch:** [Forward look, 6–18 months]

*Sources: [list]*
```

---

## STEP 4 — Write edition manifest JSON

```json
{
  "edition_num": N,
  "date": "YYYY-MM-DD",
  "title": "max 80 chars",
  "subtitle": "one-sentence hook, max 120 chars",
  "summary": "2–3 sentence plain-text summary of the edition",
  "articles": [
    {"beat": "Lead", "title": "...", "words": N},
    {"beat": "European Telecom", "title": "...", "words": N}
  ],
  "keywords": ["8–12 lowercase strings"],
  "total_words": N
}
```

Save to `editions/ed{N}_{YYYY-MM-DD}.json`.

---

## STEP 5 — Update THREADS.md

- Add any new threads from this edition's stories
- Update status/facts on existing threads
- Remove threads that have fully resolved
- Keep total file under 400 words

---

## STEP 6 — Publish to web app

```bash
curl -X POST https://agile-hope-production.up.railway.app/webhook/publish \
  -H 'Content-Type: application/json' \
  -H 'x-webhook-secret: 2e8a142d25995d892ff9f4500029c0c5' \
  -d '{
    "edition_num": N,
    "title": "...",
    "subtitle": "...",
    "date": "YYYY-MM-DD",
    "summary": "...",
    "content_md": "<full edition markdown — all articles concatenated>",
    "manifest": { <edition manifest JSON> },
    "research_topics": [
      {"topic": "...", "bullets": ["...","...","...","...","..."], "content": "...", "sources": ["...","..."]}
    ]
  }'
```

Verify response is `{"status": "published"}`.

---

## STEP 7 — Trigger email briefing

```bash
curl -X POST https://agile-hope-production.up.railway.app/webhook/send-email \
  -H 'x-webhook-secret: 2e8a142d25995d892ff9f4500029c0c5'
```

---

## STEP 8 — Commit to repo

```bash
git config user.email 'dii-agent@dii.briefing'
git config user.name 'DII Weekly Agent'
git add editions/ context/THREADS.md
git commit -m "ED{N} {date} — weekly research and articles"
git push -u origin <current-branch>
```

---

## Success criteria

- `DIGEST.md` and `THREADS.md` read before writing (not previous editions)
- 5+ research stories with bullets + narrative + sources
- 5+ articles in WSJ format, ~11,000 words total
- Each article saved to disk before writing the next
- `THREADS.md` updated with new/resolved threads
- Edition manifest JSON written
- Webhook publish returns `{"status": "published"}`
- Email endpoint called
- Committed and pushed
- End with: **edition number | article count | total word count | publish status**
