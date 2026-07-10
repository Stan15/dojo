# Growth strategy — sustained use first, virality as a consequence

_Owner-facing planning document (2026-07-09). Not a product contract. Sources
linked inline; product claims must stay true to shipped behavior (README rule)._

## 0. The honest premise

"Viral, then abandoned" is the default fate of both launch-driven dev tools
and learning apps. A [Show HN is a pulse, not a strategy](https://business.daily.dev/resources/hacker-news-marketing-developer-tools-show-hn-launch-day-sustained-coverage/)
— one day of 5k–30k visitors, then silence unless the product retains.
[Stars are vanity; converted attention is the business](https://blog.tooljet.com/github-stars-guide/).
And learning tools specifically die of a known disease: [review debt](https://wordrop.studio/blog/anki-review-debt-why-users-always-quit),
[hostile onboarding defaults](https://my-senpai.com/insights/why-people-quit-anki.html),
[engagement mechanics that fight the pedagogy](https://evakeiffenheim.substack.com/p/why-spaced-repetition-might-be-more),
and habit costs that outweigh visible benefit for months.

Dojo's strategic position is unusual: **the retention problem is already the
product's core engineering.** The debt guard, bounded packets, no-guilt
completion, honest schedule, maintenance mode, and receipts are not features
to build for growth — they are the growth story, built. What's missing is
distribution and community architecture. That's this document.

## 1. Positioning (the wedge)

**"Your AI can teach you anything. Dojo makes it stick."** — aimed at one
identity: people who learn constantly *through* AI assistants and retain
none of it. That identity is (a) painfully universal among developers,
(b) extremely online, (c) already inside the exact distribution channels
below. Secondary wedge for the SRS-native audience: *the spaced-repetition
system that refuses to bury you* — every abandonment scar named in
[why-people-quit-Anki with real answers](https://my-senpai.com/insights/why-people-quit-anki.html):

| Documented abandonment cause | Dojo's shipped answer |
|---|---|
| Review debt / queue avalanche | Debt-guarded `more`, bounded packets (I3), honest refusal with the numbers |
| 500 cards in week one, drowned by week three | Route-first entry, queue caps, JIT generation, review-before-trust |
| Bad defaults nobody tunes | No tuning needed — caps are code, not settings |
| Guilt loops / streak pressure | No-guilt ruling: push surfaces get principles, pull surfaces get numbers |
| Method opacity ("never learn the skill") | `dojo why`, `/why`, receipts, insights with provenance — the method is visible |
| Can't leave and return | Maintenance mode + honest schedule: leaving is a state, not a failure |

## 2. Channels, ranked by fit (not by size)

1. **AI-harness plugin ecosystems — the native channel.** Claude Code's
   [official marketplace vets ~100 plugins with major partners](https://www.clarista.io/blog/claude-code-mcp-plugins-guide);
   [community directories pull 300k+ devs monthly](https://claudemarketplaces.com/);
   the [recommended pattern is exactly dojo's architecture](https://codersera.com/blog/claude-skills-mcp-servers-practitioner-guide-2026/)
   — thin skills, ~30-50 tokens until invoked. Dojo's ≤60-line SKILL and
   footprint gates aren't just engineering hygiene; they're marketplace fit.
   Actions: submit to the official marketplace + top community directories;
   ship a Codex-native install path; be present in every "awesome-claude-code"
   list. This channel compounds: every new harness user is a prospective
   daily-ritual surface.
2. **The Anki community — the passion channel.** The largest, most literate
   SRS audience on earth, chronically burned by importers that mangle their
   memories. Dojo's FSRS-native import ("your memories transfer intact" —
   anki-interop.md §3) and the satellite model (§9: keep reviewing on your
   phone; dojo becomes the brain) are bridge features no competitor can offer
   honestly. r/Anki, r/spacedrepetition, the FSRS discussion orbit — arrive
   with the import demo, not a pitch.
3. **Launch pulses with substance, on a cadence.** [What works on Show HN](https://business.daily.dev/resources/hacker-news-marketing-developer-tools-show-hn-launch-day-sustained-coverage/):
   no-signup access, linked repo, founder in the comments, architecture
   depth. Dojo has unusually HN-shaped stories: "the learner model with
   receipts," "we built a holdout set so our prompts can't reward-hack,"
   "non-bombardment as a tested invariant." [Return every 12–18 months only
   with a standout update](https://business.daily.dev/resources/hacker-news-marketing-developer-tools-show-hn-launch-day-sustained-coverage/);
   between pulses, [ship visible momentum](https://www.landbase.com/blog/fastest-growing-open-source-dev-tools) —
   regular releases, honest changelogs.
4. **The benchmark flywheel — the shareable artifact.** `dojo benchmark`
   already grades any model as a *tutor* across categories. "How good is
   YOUR model at teaching?" is a natural, recurring content engine in the
   model-obsessed zeitgeist — every new model release is a reason for the
   community to run and post dojo scorecards. Low-effort: a
   BENCHMARKS.md gallery of community-submitted scorecards.
5. **Template packs — the contribution surface.** Shared campaign templates
   ("TEF French in 90 days", "SRE interview prep", "read ML papers
   without skipping the stats") as plain markdown packs. [Community content
   outpacing official content is the signature of durable OSS growth](https://www.rzlt.io/blog/open-source-marketing-how-to-turn-a-github-repo-into-a-growth-engine);
   packs are dojo's version — cheap to contribute, immediately useful,
   inherently shareable. Plus AnkiWeb shared-deck publishing (interop §4.5)
   as a zero-code secondary surface.

## 3. Time-to-magic (the funnel's only KPI that matters early)

Install → "I want to learn X" → first calibrated session, **under five
minutes, zero config** — already true on the happy path; protect it as a
tested invariant the way budgets are. The README's opening demo block is the
single highest-leverage growth asset: turn it into a 30-second GIF/asciinema
showing capture → route → daily → `/why` → the receipts. [Products that can
be tried without signup outperform on every dev channel](https://business.daily.dev/resources/hacker-news-marketing-developer-tools-show-hn-launch-day-sustained-coverage/).

## 4. Sustained use — mechanics we will and won't use

- **The harness IS the habit anchor.** Dojo doesn't need to build a
  notification system: it lives inside the tool the user already opens
  daily. Lean in: a first-class scheduled-agent recipe ("your agent runs
  dojo daily at 9am and greets you with the packet") — the habit rides an
  existing one, the strongest known habit-formation move.
- **Return-without-guilt as a retention feature.** Most SRS churn is
  shame-avalanche churn. Dojo's honest schedule means a two-week absence
  returns a sane packet, not 400 reviews. SAY THIS in the README —
  it converts exactly the burned users channel #2 reaches.
- **No dark patterns, stated as policy.** No streak pressure, no
  solicitation, no engagement theater — the owner rulings are already
  encoded. Publish them as a "product ethics" doc section; the
  anti-Duolingo positioning is load-bearing for the audience we want and
  [the engagement-vs-pedagogy conflict is well documented](https://evakeiffenheim.substack.com/p/why-spaced-repetition-might-be-more).
- **No telemetry.** Local-first privacy is part of the trust story. Measure
  with proxies (installs via marketplaces, pack downloads, GitHub traffic)
  and an opt-in `dojo stats --share` someday, never phone-home.

## 5. Community architecture (the sustain engine)

- **Radical transparency is already our workflow — publish it.** STATE.md,
  QUESTIONS.md-with-defaults, INSIGHTS.md, the holdout protocol: as a public
  repo these become a living case study that generates its own audience
  ([community-governed, visibly-alive projects out-compound funded ones](https://www.xda-developers.com/open-source-developer-tools-that-are-better-than-their-competitors/)).
- **Contribution ladders**: template packs (easiest) → eval corpus scenarios
  (gated by the shape suite; the holdout protocol makes "write scenarios"
  a real, protected contribution class) → store-format ecosystem tools
  (webviews, mobile readers — the markdown contract is an API).
- **Release rhythm**: small versioned releases with honest notes;
  [consistent cadence is what converts watchers to adopters](https://www.landbase.com/blog/fastest-growing-open-source-dev-tools).

## 6. Sequenced plan

**Phase 0 — prerequisites (before any public pulse):** run the holdout gate,
tag v1.0.0; repo public; docs site hosted; README demo GIF; CONTRIBUTING.md
with the pack/corpus ladders; 3–5 seed template packs authored.
**Phase 1 — soft channels (weeks 1–4):** marketplace + directory listings;
Codex install path; 2–3 deep-dive posts (receipts, holdout, non-bombardment)
seeded to the AI-tools newsletter orbit; benchmark gallery opened.
**Phase 2 — the pulse (when Phase 1 shows organic pull):** Show HN with the
no-guilt + receipts story, founder present all day; simultaneous r/Anki post
anchored on the import demo (requires interop A1 shipped — promote it).
**Phase 3 — compound (quarterly):** substantive update pulses; community
scorecards after each model release; packs showcase; return to HN only with
a genuine milestone.

**The order of operations bet**: channel #1 (marketplaces) sustains between
pulses because it's where the daily habit already lives; channel #2 (Anki)
supplies the passionate early community every durable OSS project needs; the
launch pulse is deliberately LAST — spikes only convert when the retention
surface underneath them is finished, and ours is.
