# Anki interop — product investigation & solution plan (PROPOSAL)

_Status: investigation delivered 2026-07-09 (owner-directed: "investigate like a
product manager as well as a principal engineer"). Extends ADR 015; nothing here
is scheduled until the owner promotes it. Architecture by Fable; web research
2026-07-09._

## 1. The product question

Owner framing: "not sure if Anki connectivity is possible, feasible, or ideal —
I just think it would be a really cool selling point, reaching the users where
they are at."

**Verdict up front: possible — yes; feasible — yes, bounded and cheap if scoped
right; ideal — as an acquisition adapter, yes; as a sync surface, no (ADR 015's
argument stands, and 2026 evidence strengthens it).**

## 2. Who the users are (PM lens)

- Anki is the largest spaced-repetition community in the world: ~[86% of US
  medical students](https://pmc.ncbi.nlm.nih.gov/articles/PMC10563486/) use it
  (66% daily), plus large language-learning / exam / professional segments;
  [AnkiWeb hosts 100k+ shared decks](https://noun.town/blog/is-anki-still-worth-using-in-2026/).
- Their sunk cost is not the cards — it's the **review history**: years of
  consolidated memory state. Any tool that drops it re-teaches known material;
  users experience that as insulting, and they say so in migration threads.
- Migration is a proven funnel: [RemNote](https://help.remnote.com/en/articles/6751471-importing-from-anki)
  and [Mochi](https://mochi.cards/docs/import-and-export/importing/) both import
  .apkg *including scheduling history*; Deckbase built its acquisition page
  around bulk Anki import. **Scheduling-state import is table stakes for
  conversion**; notes-only import converts nobody with a mature collection.
- What draws an Anki user to dojo (things Anki cannot do): goal-driven
  campaigns, AI-generated + rubric-graded exercises (skills, not just recall),
  the evidence loop → insights with receipts, agent-driven practice. What
  repels: losing decks/history, losing phone review (AnkiMobile habit).

## 3. The 2026 fact that changes the pitch

Anki itself adopted **FSRS** as its scheduler; modern collections store
per-card FSRS `memory_state` (stability, difficulty) — see
[Anki's memory-state management](https://deepwiki.com/ankitects/anki/4.4-memory-state-management-and-rescheduling)
and the [FSRS FAQ](https://faqs.ankiweb.net/what-spaced-repetition-algorithm).
Dojo schedules with **py-fsrs, the same FSRS-6 model family** (ADR 014).

Consequence: competitors import Anki cards into *alien* schedulers (fidelity
loss they must apologize for). Dojo can honor Anki's own memory state almost
**losslessly** — stability/difficulty map directly onto py-fsrs Card state.
"Your memories transfer intact" is a differentiated, honest selling point no
non-FSRS competitor can make.

## 4. Connectivity option space (engineering lens)

| Shape | Feasible? | Verdict |
|---|---|---|
| 1. One-time `.apkg` import | Yes — .apkg is a zip holding a SQLite db; legacy `collection.anki2` readable with **stdlib only** (zipfile+sqlite3+json). Newer `.anki21b` is zstd/protobuf — require "support older Anki versions" export in v1 (one checkbox, documented) | **Build.** The acquisition adapter |
| 2. One-way export (dojo → .apkg) | Yes — [genanki](https://github.com/kerrickstaley/genanki) (MIT, still the standard; stable deck/model IDs + GUIDs for re-import dedupe) | **Build second.** Serves the phone-review habit; ADR 015 custody rules apply |
| 3. AnkiConnect (local HTTP into running desktop Anki) | Works ([API incl. apkg import/export](https://git.sr.ht/~foosoft/anki-connect)) but requires desktop Anki running; wrong for a CLI/agent-first product | **Reject** — and it drags toward live sync |
| 4. AnkiWeb sync protocol / anki-sync-server | Exists (official self-hosted server) but makes dojo an Anki *backend*: maximal maintenance, two schedulers over one memory set | **Reject** (ADR 015's core argument) |
| 5. Publish dojo-made decks to AnkiWeb shared decks | Zero code beyond #2 — users share exported decks | Free growth channel; note, don't engineer |
| 6. Live coexistence (Anki keeps authority, dojo reads revlog) | Technically possible; evidence loop gains nothing it can act on (no error tags, no latency, no learner answers) | **Reject** — all cost, no pedagogy |

Library note: the official `anki` pip package (pylib) is powerful but drags the
Rust backend and tight version pins — wrong weight for dojo. Third-party readers
(ankisync2, AnkiTools) are thinly maintained. A ~150-line **owned read-only
parser** over the legacy schema is the dependency-light move, fixture-tested
against real exports.

## 5. The product risk that shapes everything (why scoped, not bulk)

Dojo is not a flashcard warehouse. A 20k-card AnKing collection dumped into a
5-8 item daily packet is structural dishonesty — the debt guard would refuse
extensions forever and the queue cap would silently discard consolidated
memories (already a ledgered defect vector). **Bulk collection import is the
feature that would kill the product's honesty.** Therefore:

- Import is **deck-scoped and campaign-scoped**: one deck → one campaign (or
  extend an existing one via the route-first flow). "Bring the deck that serves
  your current goal", never "mirror your collection".
- Import volume respects the queue cap; overflow stays in candidates
  (unattempted stock is exactly what `dojo more`'s sourcing order wants).
- Import report is honest: n notes imported, n skipped (media, unparseable),
  cloze expansion counts, and — when scheduling state came along — "your review
  history is respected: nothing will be re-taught."

## 6. Solution plan (bounded milestones, each independently shippable)

**A1 — `dojo import anki <deck.apkg>`** (~2-3 sessions)
- Owned stdlib parser: zip → `collection.anki2` SQLite → notes/cards/decks
  (+ `memory_state` when present; else `ivl`/`factor`/`due`).
- Notes → a Source (provenance: deck name, note ids — capture/locator
  machinery) + recall candidates, fronts/backs **verbatim**
  (extract-never-enrich). Cloze notes → one item per cloze index. HTML
  stripped to text; media skipped v1 (dojo is text-first); both reported.
- Scheduling fidelity ladder, in order of what the deck provides:
  (a) FSRS `memory_state` present → map stability/difficulty/due directly
  onto py-fsrs state (the lossless pitch, §3);
  (b) SM-2 fields only → seed approximate FSRS state from ivl/factor
  (documented approximation, marked in provenance);
  (c) nothing → new material, normal candidate path.
  Full revlog→optimizer personalization is A3, only if demand pulls.
- Enters via the route-first grammar: `dojo learn --from-deck <apkg> "<goal>"`
  or plain `dojo import anki` creating/extending a campaign with consent.
- Fixtures: real .apkg exports (basic, cloze, FSRS-era, sub-decks, unicode)
  round-tripped in tests; store contract untouched (items are items).

**A2 — `dojo export anki [--campaign]`** (~1 session)
- genanki as an optional extra (like `[pdf]`); recall items → basic notes;
  GUID = stable hash of item id (re-export updates, never duplicates).
- ADR 015 custody: exported items marked `custody: external`, dojo **stops
  scheduling them**, and the export says so at the moment it happens.

**A3 — revlog-based FSRS parameter personalization** (parked; needs
fsrs-optimizer, torch-class dependency — wrong weight until proven demand).

## 7. Honest failure modes (so the selling point stays honest)

- Format drift: Anki's newer packages change; v1 pins the legacy-compat export
  path (one documented checkbox) + fixture suite. Parser failures must name the
  fix ("re-export with 'Support older Anki versions'").
- Formatting fidelity complaints are the #1 import-support burden for
  Mochi/RemNote (HTML/CSS templates don't translate). Dojo's answer is honest
  scope: text extracted verbatim, complex templates reported as skipped —
  never mangled silently.
- Two-scheduler temptation will return as a feature request the day export
  ships. ADR 015 is the standing answer; custody is binary and visible.

## 8. Decisions waiting on the owner

1. Promote A1 (import) into the active milestone queue, or keep parked?
2. Import grammar: unified under `dojo learn` route-first, separate
   `dojo import anki`, or both (recommendation: both — one mechanism)?
3. v1 scheduling fidelity: ladder as specced (a+b), or notes-only first?
4. genanki optional-extra policy for export (A2).

## 9. The sync question, pressed (owner, 2026-07-09): the satellite model

§4 rejected two sync-adjacent shapes; the owner's follow-up ("investigate
**syncing**") deserves the third shape examined on its merits, because it is
neither of the rejected ones:

- Option 6 rejected "Anki keeps authority, dojo reads revlog." The satellite
  inverts custody: **dojo keeps authority; Anki is a rendering device.**
- Option 3 rejected AnkiConnect as *required* infrastructure. The satellite
  needs no live bridge: it composes from A1/A2's own parts (apkg export out,
  revlog read back from the collection/exported file); AnkiConnect becomes an
  optional convenience transport when desktop Anki is present, never a
  dependency.

**The mechanism** (recall lane only — skills are novel-per-session, ADR 007,
nothing to sync):
1. Content, one way (dojo → Anki): due recall items push into a
   machine-managed `Dojo::<campaign>` deck; note guid = exercise id (A2's
   dedupe machinery, reused). Dojo also writes the DUE DATES it computed —
   Anki displays dojo's schedule instead of running its own over these cards.
2. Outcomes, one way (Anki → dojo): the revlog rows for dojo-guid cards pull
   back as Attempts — ease maps to score bands (Again 0.0 · Hard 0.7 ·
   Good/Easy 1.0), latency from revlog ms, `origin: "anki"` (the extension-
   channel pattern) — and `outcomes.land_score` advances **dojo's** FSRS.
   Contra option 6's "no pedagogy": score+latency is precisely what the
   scheduler consumes, and reflection reads the rows (without answer
   glimpses or error tags — an honest, marked signal reduction, identical to
   what custody-export loses *entirely*).
3. Divergence is self-healing: reviewed early/late in Anki → the revlog says
   so → dojo reschedules → next push re-aligns Anki. One brain, eventually
   consistent, no merge algebra.

**Why this matters against §6's A2 custody rule**: binary custody
("exported items leave dojo's brain") answers the two-scheduler problem by
amputation — the moment a user wants phone review, their most-practiced facts
EXIT the evidence loop forever. For a product whose differentiator is that
loop, custody-export bleeds it precisely for the most engaged users. The
satellite keeps them.

**Costs, honestly**: a sync step in the heartbeat (push dues / pull revlog
when linked); machine-managed-deck rules users must accept (edits overwritten
on push; content changes belong in dojo); file-transport mode needs access to
the Anki collection or a re-exported file (documented flow), with AnkiConnect
as the zero-friction path when available. Estimate: ~2-4 focused days on top
of A1+A2 (parser, genanki, guid discipline all shared).

**Recommendation (PM+eng)**: sequence A1 (import) unchanged; ship A2 in
**satellite mode as the default** (custody-export remains as an explicit
`--handoff` for users leaving); write ADR 017 amending 015: "no *symmetric*
sync" stays; asymmetric satellite adopted. This also upgrades §8's decision 4
and adds:
5. A2 default mode: satellite (recommended) vs binary custody handoff?
