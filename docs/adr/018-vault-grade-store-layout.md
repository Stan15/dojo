# ADR 018: Vault-Grade Store Layout (journal out of frontmatter)

## Status
Accepted (2026-07-10). Owner directive: the markdown store must be readable
"as an Obsidian vault — cleanly and expressively"; massive frontmatter values
are "EXTREMELY inelegant." Approved contingent on the investigation below
("if [no surface justifies full text] then i definitely agree").

## Context — measured on the owner's live store

One-day-old campaign: campaign.md was **87% frontmatter** (10.7KB of 12.4KB);
`pedagogical_journal` alone 6.4KB and unbounded (every phase advance embeds a
full plan + syllabus + hypotheses snapshot). The attack plan was persisted in
three places (campaign.md frontmatter, plan.yaml, changelog.md frontmatter —
the last of which silently *won* on read). Blueprint §5 already prescribed
plan.yaml / topics.yaml / journal.md projections; the implementation drifted.

## The investigation: what actually reads the journal?

Every consumer enumerated (grep-verified, 2026-07-10):

| Journal field | Readers | Verdict |
|---|---|---|
| timestamp/action/trigger/hypothesis/status | campaign history API, changelog prose, last-reflect timestamp, learn-extend dedup | prose-sized, keep |
| `announced`, `insights_changed` | daily announce-once notices | small flags, keep |
| task id in trigger / `run_trace` | task housekeeping provenance | small, keep |
| `plan_snapshot` on CREATE / PLAN_CONFIRMED / PLAN_REVERTED / PLAN_APPLIED | authority baseline (anti-drip), `dojo plan revert` | FUNCTIONAL — keep, bounded (one plan per plan-act) |
| `proposed_phases` + pending status | `dojo plan confirm/reject` applies phases from the entry | FUNCTIONAL — keep |
| `syllabus_snapshot` | **nothing** | write-only bloat — delete |
| `hypotheses_snapshot` | **nothing** | write-only bloat — delete |
| `performance_snapshot` | **nothing** (trigger text already carries the numbers) | write-only bloat — delete |
| `plan_snapshot` on PHASE_ADVANCE | **nothing** (not a baseline action, not revertable) | delete |

**Conclusion: no surface justifies full-text journal entries.** Displays
consume five prose fields; the functional reads are small flags plus two
bounded plan-authority structures.

## Decision

Campaign aggregate becomes five files; campaign.md frontmatter holds ONLY
scalar identity/config (~10 lines):

```
campaigns/camp_<id>/
  campaign.md      # id, name, mission, status, phase, strategy — body: syllabus
  plan.yaml        # the attack plan (canonical; hand-edits win, as today)
  topics.yaml      # topic registry + FSRS state (machine bookkeeping out of the note)
  journal.md       # append-only PROSE projection, newest-first (regenerated on save)
  .journal.yaml    # the machine event log (lean entries; hidden from vaults —
                   #  Obsidian ignores dotfiles). Canonical for the journal.
```

- `attack_plan`, `topics`, `pedagogical_journal` never serialize into
  campaign.md frontmatter (engine-level exclusion); the in-memory Campaign
  model and every API above the store are unchanged.
- `.journal.yaml` preserves the authority state machine byte-for-byte
  (baseline / pending proposal / revertable walk exactly as before) —
  functional state does NOT move to git refs: store git commits are
  advisory (doctor-surfaced, can fail); availability of consent machinery
  must not depend on them.
- `journal.md` is a display projection; hand-edits to it are not folded
  back (they never were — changelog.md frontmatter already won). plan.yaml
  and topics.yaml remain hand-editable canonical.
- Writers stop emitting the four dead fields; `save()` also strips them
  from historical entries (delete-over-retain: git is the archive).
- changelog.md is deleted on first save (superseded by journal.md).

## Migration

Readers understand the legacy shape (frontmatter / changelog.md
`journal_entries`); every save writes the new shape; `dojo doctor` re-saves
all campaigns once and reports "migrated N campaign(s) to the vault layout."
The owner's live store migrates on the next doctor/install or naturally on
first write per campaign.

## Deferred (phase 2, needs id↔filename harmonization)
Obsidian wikilinks between entity files (`[[att_…]]` in insight bodies) —
valuable, but link resolution needs filenames to match ids; ledgered.

## Consequences
Blueprint §5 layout + format rules updated same commit. Store conformance
and golden fixtures updated: frontmatter contract for campaigns now excludes
the three projected fields. Public-contract change: fixture round-trip tests
accompany (I7).
