"""Filing a routed capture (ADR 013): the deterministic half of routing.

The AI proposes (capture.route task); a human confirms (Q6 default) or
`capture.autofile` lets high-confidence routes through — then THIS code files:
the capture becomes an ordinary Source (the smallest one), attached to its
campaign, with the topic registered and an optional seed exercise requested.
No parallel pipeline: from here on it's a source like any other.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .schemas import Campaign, Capture, Source
from .store import slugify


def known_topic_paths(store, campaign: Campaign) -> set[str]:
    """Every topic path that verifiably exists in a campaign (registry +
    exercise topics + the root) — the set a route may attach to."""
    paths = {t["path"] for t in (campaign.topics or []) if t.get("path")}
    paths |= {ex.topic_path for ex in store.exercises.list(campaign.id)}
    if campaign.topic_path:
        paths.add(campaign.topic_path)
    return paths


def file_capture(store, capture: Capture, proposal: dict[str, Any]) -> dict[str, Any]:
    """Materializes a validated route proposal. Idempotent: source id derives
    from the capture id, re-filing overwrites rather than duplicates."""
    from .tasks import flows  # local: avoids a module cycle

    action = proposal["action"]
    now = datetime.now(timezone.utc).isoformat()

    if action == "propose_campaign":
        campaign_id = slugify(proposal["new_name"])
        campaign = store.campaigns.get(campaign_id)
        if campaign is None:
            campaign = Campaign(
                id=campaign_id,
                name=proposal["new_name"],
                mission=proposal["new_mission"],
                topic_path=slugify(proposal["new_name"]).replace("-", "_"),
                # Parity with every other creation door (owner audit
                # 2026-07-18, Q 6g): a brand-new campaign starts calibrating.
                strategy_profile={"difficulty": "intermediate",
                                  "scaffolding": "medium", "mode": "diagnostic"},
            )
        topic_path = proposal.get("topic_path") or campaign.topic_path
    else:
        campaign = store.campaigns.get(proposal["campaign"])
        if campaign is None:
            raise ValueError(f"campaign {proposal['campaign']!r} not found")
        topic_path = proposal["topic_path"]

    source = Source(
        id=f"src_{capture.id.removeprefix('cap_')}",
        title=(capture.text.strip().splitlines()[0][:60] or "captured note"),
        kind="capture",
        path=capture.locator,  # provenance survives filing (URL/file the agent read)
        mission=capture.why,
        content=capture.text,
    )
    store.sources.save(source)

    if not any(t.get("path") == topic_path for t in campaign.topics):
        campaign.topics.append({"path": topic_path, "kind": "recall", "summary": ""})
    if not any(link.get("source_id") == source.id for link in campaign.sources_config):
        campaign.sources_config.append({
            "source_id": source.id,
            "purpose": "captured note",
            "topics": [topic_path],
        })
    campaign.updated_at = now
    store.campaigns.save(campaign)

    task_refs = []
    next_hint = None
    if action == "propose_campaign":
        # A capture-born campaign no longer dead-ends bare (owner core-need
        # 2026-07-18, Q 6g): chain the same plan pipeline `dojo learn` uses,
        # seeded with the router's mission and the learner's why + material.
        # Review-before-trust holds: the plan applies nothing until the
        # learner materializes it INTO this campaign.
        why_bit = f" (why it matters to the learner: {capture.why})" if capture.why else ""
        plan_task = flows.request_plan(
            store, goal=proposal["new_mission"],
            context_notes=f"planned from a captured note{why_bit}: {capture.text[:400]}",
            existing_topics=flows.registry_topic_paths(store),
        )
        task_refs.append(flows.task_ref(plan_task))
        next_hint = (
            f"fulfill the plan task, review it (dojo task show {plan_task.id}), "
            f"then: dojo campaign create --from-task {plan_task.id} --into {campaign.id}"
        )
    if proposal.get("seed"):
        task = flows.request_generation(
            store, campaign,
            topic_path=topic_path, n_items=1, source_slice=capture.text,
            # The learner's stated reason travels into the generation payload:
            # practice aims at what THEY care about in the material, not the
            # material generally (owner core-need audit 2026-07-18, Q 6g).
            source_why=capture.why,
        )
        task_refs.append(flows.task_ref(task))

    capture.status = "filed"
    capture.source_id = source.id
    capture.updated_at = now
    store.captures.save(capture)

    return {
        "capture_id": capture.id,
        "source_id": source.id,
        "campaign_id": campaign.id,
        "topic_path": topic_path,
        "tasks": task_refs,
        **({"next": next_hint} if next_hint else {}),
    }
