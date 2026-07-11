# Demo shots — the GIFs the README is waiting for

Each shot is scripted so it can be re-recorded when the UI evolves.
Recommended tooling: [vhs](https://github.com/charmbracelet/vhs) (scriptable
`.tape` files → deterministic GIFs) or asciinema + agg. House style: 100×28
terminal, a dark theme, 16-18pt font, **≤ 2 MB per GIF** (GitHub renders
inline), 1-2s pauses on the moments that matter. Record against a throwaway
store (`dojo --db /tmp/demo-store …`) seeded fresh for each take.

---

## Shot 1 — "Time to magic" *(the README opener — record this one first)*

**Placement:** README top, right after the opening transcript.
**Target:** ≤ 45 seconds. The whole promise: from "I want to learn X" to
answering a real calibrated question, zero config.

Script:
1. `dojo learn "conversational French, TEF exam Oct 12"` — pause on the
   routed goal + emitted task.
2. Agent fulfills (or `dojo task run` with a configured model) — show the
   mission + lean topic plan + one refinement question appearing.
3. `dojo campaign create --from-task tsk_…` — confirm.
4. `dojo daily` — first calibration question appears; type a short answer.
5. End on the session panel with the second prompt visible.

Money moment: the gap between step 1 and a real question being asked — count
the seconds on screen.

## Shot 2 — "The daily ritual" *(the product's face)*

**Placement:** README "The daily loop" section.
**Target:** ≤ 35 seconds.

Script (seed: one campaign mid-flight, one due review, one ☆ study card, one
question you'll get wrong):
1. `dojo daily` — packet appears.
2. Answer the review correctly — ✓.
3. The ☆ study card: pause 2s on "read it, own it — Enter to continue".
4. Type `/why` mid-question — the honest one-line reason prints inline.
5. Miss the last question — show the grade + **the answer reveal** (nothing
   scored against you on first contact).
6. End on the session summary.

Money moments: the ☆ card (teaching, not quizzing) and the miss that doesn't
punish.

## Shot 3 — "Receipts" *(the learner model is inspectable and contestable)*

**Placement:** README "Your learner model, with receipts".
**Target:** ≤ 25 seconds.

Script (seed: a campaign with 2-3 insights, one wrong):
1. `dojo insights` — the beliefs list.
2. `dojo insights show ins_…` — pause on the verbatim quote of YOUR answer
   behind the belief.
3. `dojo insights resolve ins_… --because "I know this — I was rushing"` —
   your words land, belief resolved.

Money moment: the system quoting the user's own words as evidence.

## Shot 4 — "Watch your model think" *(the benchmark live pane)*

**Placement:** README "Benchmark your model".
**Target:** ≤ 30 seconds.

Script:
1. `dojo benchmark -d "ollama run gemma3:1b" --tier compliance` — the live
   pane appears: anchored header, streaming model output, tok/s climbing.
2. Let 2-3 scenarios stream — the reasoning text scrolling IS the shot.
3. Cut to the final category scorecard with its bars.

Money moment: tokens/sec ticking live while raw model thought streams below.
(A 1B model is ideal here — fast enough to look alive in a GIF.)

## Shot 5 — "Come back without guilt" *(the anti-Anki shot)*

**Placement:** README "Why it works" bullet on sustainability, or the launch
post.
**Target:** ≤ 20 seconds.

Script (seed: a store whose last attempt is 14+ days old, many nominally-due
reviews):
1. `dojo daily` — a SANE, small packet appears (not 400 reviews).
2. `dojo why` — the honest explanation: caps, interleaving, no punishment.

Money moment: "14 days away" visible, packet of five, zero guilt copy.

## Shot 6 — "It's just markdown" *(local-first trust)*

**Placement:** README top section ("plain markdown files you can open").
**Target:** ≤ 20 seconds. Can be a static screenshot instead of a GIF.

Script:
1. Open `~/.local/share/dojo/` as an Obsidian vault (or `ls` + `cat`).
2. Show `campaign.md` (clean frontmatter + syllabus), `journal.md` (prose),
   one attempt file with your verbatim answer.
3. `git log --oneline` in the store — every session remembered.

Money moment: the journal reading like a human diary of your learning.

---

## After recording

Replace each `> 🎬 Demo GIF coming…` placeholder in the README with the GIF
(`![demo](docs/gifs/<name>.gif)`), keep the `.tape`/script files in
`docs/gifs/` beside them, and delete this file's entry for the shot (this
list should shrink to empty and then be deleted — delete-over-retain).
