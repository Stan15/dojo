"""Human-facing interactive flows (owner directive 2026-07-08).

Two audiences, one core: agents get the JSON envelope protocol and are NEVER
blocked on input (cli._use_json guards every entry); humans at a TTY get flows
— AI tasks drain inline through the configured `fulfiller.command` with a
spinner, practice runs as one continuous loop, and proposals confirm with a
keypress. Everything here calls the same DojoAPI / task service the agent path
uses; this module renders and sequences, it never owns logic.
"""
from __future__ import annotations

import shlex
import subprocess
from typing import Any, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .api import DojoAPI
from .tasks import service

console = Console()


import sys


def _input(prompt: str) -> str:
    """The single interactive entry — tests patch this; the agent path must
    never reach it (cli._use_json guards every entry). Defense in depth: if it
    is ever reached without a real terminal, fail loudly and instantly rather
    than hang a piped agent forever (owner directive 2026-07-08)."""
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise RuntimeError(
            "interactive prompt reached without a terminal — this is a dojo bug; "
            "agents must pass --json (re-run the command with --json)"
        )
    return console.input(prompt)


def confirm(question: str, default: bool = True) -> bool:
    """Y/n keypress with a default; empty input takes the default."""
    suffix = "[Y/n]" if default else "[y/N]"
    answer = _input(f"{question} [bold]{suffix}[/bold] ").strip().lower()
    if not answer:
        return default
    return answer.startswith("y")


def fulfiller_command(api: DojoAPI) -> Optional[str]:
    """The configured one-string local model command, or None."""
    return api.store.configs.get_value("fulfiller.command")


def explain_no_fulfiller() -> None:
    """Tells the human their two options when an AI step has no fulfiller:
    drive dojo from an agent, or set `fulfiller.command` once."""
    console.print(
        "\n[yellow]This step needs an AI and no fulfiller is configured.[/yellow]\n"
        "Either drive dojo from your AI agent (it fulfills tasks itself), or set\n"
        "a one-string local model command once:\n"
        '  [bold]dojo config set fulfiller.command "codex exec"[/bold]   # or "ollama run llama3"\n'
    )


def drain_tasks(api: DojoAPI, task_refs: list[dict[str, Any]], *, timeout: int = 300) -> bool:
    """Fulfills pending tasks inline via fulfiller.command. Returns True when
    every task applied; failures are shown honestly and False returned."""
    command = fulfiller_command(api)
    if not command:
        explain_no_fulfiller()
        return False
    ok = True
    for ref in task_refs:
        task = api.store.tasks.get(ref["id"])
        if task is None or task.status != "pending":
            continue
        label = task.kind.replace(".", " · ")
        with console.status(f"[cyan]thinking[/cyan] ({label})…", spinner="dots"):
            try:
                proc = subprocess.run(
                    shlex.split(command), input=task.prompt,
                    capture_output=True, text=True, timeout=timeout,
                )
                outcome = service.submit(api.store, task.id, proc.stdout)
            except Exception as exc:  # timeout, missing binary, …
                console.print(f"  [red]✗ {task.id}: {str(exc)[:120]}[/red]")
                ok = False
                continue
        if not outcome.ok:
            console.print(f"  [red]✗ {task.id}: {'; '.join(outcome.errors[:2])[:160]}[/red]")
            ok = False
    return ok


# ------------------------------------------------------------------
# Practice: one continuous session loop
# ------------------------------------------------------------------

def practice_loop(api: DojoAPI, session: dict[str, Any]) -> None:
    """Runs a session as one continuous conversation: reveal → answer →
    next, with `/skip <reason>` and `/quit` (pause; daily resumes). Free-form
    answers grade in ONE batch at the end (D1 — a model call between
    questions stalls the human), then a stats summary prints."""
    total = len(session["exercise_ids"])
    done = session.get("current_index", 0)
    console.print(f"\n[bold]Session[/bold] — {total - done} prompt(s) to go. "
                  "[dim](/skip too_easy|too_hard|forgot|bad_quality, /quit)[/dim]\n")
    # Free-form answers grade at the END, in one batch: a model call between
    # every question stalls the human's flow, and scores never gated
    # progression anyway (use-case audit D1).
    pending_grades: list[dict[str, Any]] = []
    while True:
        try:
            info = api.reveal_prompt(session_id=session["id"])
        except ValueError:
            break
        done += 1
        console.print(Panel(info["prompt"], title=f"[bold]{done} of {total}[/bold]",
                            border_style="cyan"))
        answer = ""
        while not answer.strip():
            answer = _input("[bold cyan]›[/bold cyan] ")
        if answer.strip() == "/quit":
            console.print("[dim]Paused — dojo daily resumes right here.[/dim]")
            _settle_grades(api, pending_grades)
            return
        if answer.strip().startswith("/skip"):
            parts = answer.strip().split()
            reason = parts[1] if len(parts) > 1 else "forgot"
            res = api.skip_active_exercise(reason, session_id=session["id"])
            console.print(f"  [yellow]skipped ({reason})[/yellow]\n")
        else:
            res = api.submit_answer(user_answer=answer, session_id=session["id"])
            if res.get("pending_grade") and res.get("tasks"):
                pending_grades.append(res)
                console.print("  [dim]✓ recorded — scoring at the end[/dim]\n")
            else:
                correct = res.get("correct_answer")
                _print_score(res["score"], None if res["score"] >= 1.0 else
                             (f"answer: {correct}" if correct else None))
        if res.get("is_session_completed"):
            break
    console.print("[bold green]Session complete.[/bold green]")
    _settle_grades(api, pending_grades)
    _session_summary(api)


def _settle_grades(api: DojoAPI, pending: list[dict[str, Any]]) -> None:
    if not pending:
        return
    console.print(f"[bold]Scoring {len(pending)} answer(s)…[/bold]")
    drained = drain_tasks(api, [t for res in pending for t in res["tasks"]])
    for res in pending:
        attempt = api.store.attempts.get(res["campaign_id"], res["attempt_id"])
        if attempt.grader == "ai":
            _print_score(attempt.score, attempt.grade_feedback)
        else:
            console.print("  [yellow]grade still pending — an agent (or dojo task run) can finish it[/yellow]\n")
    if not drained:
        console.print("  [dim]dojo daily will re-surface unfinished grades tomorrow[/dim]")


def _print_score(score: float, note: Optional[str]) -> None:
    if score >= 1.0:
        console.print("  [bold green]✓ correct[/bold green]\n")
    elif score >= 0.7:
        console.print(f"  [yellow]◐ nearly ({score:.1f})[/yellow]"
                      + (f" [dim]{note}[/dim]" if note else "") + "\n")
    else:
        console.print(f"  [red]✗ not yet ({score:.1f})[/red]"
                      + (f" [dim]{note}[/dim]" if note else "") + "\n")


def _session_summary(api: DojoAPI) -> None:
    stats = api.stats()
    table = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
    for col in ("Campaign", "Retention*", "Due", "Accuracy"):
        table.add_column(col)
    for c in stats["campaigns"]:
        ret = "—" if c["estimated_retention"] is None else f"{c['estimated_retention']:.0%}"
        acc = "—" if c["recent_accuracy"] is None else f"{c['recent_accuracy']:.0%}"
        table.add_row(c["name"], ret, f"{c['due_now']}/{c['active_exercises']}", acc)
    console.print(table)
    console.print("  [dim]*estimated recall odds · dojo why explains today's picks[/dim]")


def daily_flow(api: DojoAPI, size: Optional[int] = None, reset: bool = False) -> int:
    """The human `dojo daily`: builds the packet, drains blocking generation
    tasks inline (at most drain → rebuild → drain, covering the cold-start
    diagnostic round), then hands off to `practice_loop`. Exits gracefully
    with printed task handles when no fulfiller is configured."""
    res = api.daily(size=size, reset=reset)
    for change in res.get("plan_changes", []):
        console.print(f"[yellow]Plan updated[/yellow] ([cyan]{change['campaign_id']}[/cyan]): "
                      f"{change['reason']}  [dim]{change['undo']}[/dim]")
    for prop in res.get("plan_proposals", []):
        console.print(f"[yellow]Plan restructure proposed[/yellow] "
                      f"([cyan]{prop['campaign_id']}[/cyan]): {prop['reason']} — "
                      f"[bold]dojo plan show[/bold] to review")
    for _ in range(2):  # at most: drain → rebuild → drain (cold-start diagnostic round)
        if res.get("session") is not None:
            break
        if not res.get("tasks"):
            console.print(f"[green]Nothing due — {res.get('next', 'enjoy the day off')}[/green]")
            return 0
        if not drain_tasks(api, res["tasks"]):
            for t in res["tasks"]:
                console.print(f"  pending: [cyan]{t['id']}[/cyan] — {t['submit_with']}")
            return 0
        res = api.daily(size=size)
    if res.get("session") is None:
        console.print("[yellow]Still nothing practicable — check dojo stats / dojo inbox.[/yellow]")
        return 0
    if res.get("tasks"):
        drain_tasks(api, res["tasks"])  # background replenishment, non-blocking
    if res.get("inbox_waiting"):
        console.print(f"[dim]{res['inbox_waiting']} capture(s) awaiting a home — dojo inbox[/dim]")
    practice_loop(api, res["session"])
    return 0


# ------------------------------------------------------------------
# Plan → refine → create, one conversation
# ------------------------------------------------------------------

def _render_proposal(proposal: dict[str, Any]) -> None:
    lines = [f"[bold]{proposal['mission']}[/bold]", ""]
    for t in proposal["topics"]:
        lines.append(f"  [cyan]{t['path']}[/cyan] [dim]({t['kind']}) {t.get('summary', '')}[/dim]")
    lines.append("")
    for p in proposal["phases"]:
        crit = p["criteria"]
        lines.append(f"  Phase {p['phase']}: {', '.join(p['topics'])} "
                     f"[dim]({crit['min_attempts']}+ attempts @ {crit['min_accuracy']:.0%}"
                     + (f" — {p['focus']}" if p.get("focus") else "") + ")[/dim]")
    console.print(Panel("\n".join(lines), title="[bold green]Proposed campaign[/bold green]",
                        border_style="green"))


def plan_flow(api: DojoAPI, *, goal: str, level: Optional[str], context: Optional[str],
              emit_plan_task, materialize, initial_task_ref: Optional[dict] = None) -> int:
    """Plan → refine → create as one conversation: renders the proposal,
    walks the model's refinement questions (answers trigger one re-plan),
    and only materializes a campaign on explicit confirmation. Declining
    keeps the fulfilled task as a proposal (`campaign create --from-task`).
    `emit_plan_task(goal, notes)` and `materialize(task_id)` are injected by
    the CLI to avoid owning command wiring here; `initial_task_ref` continues
    from an already-emitted plan task (the learn flow's handoffs) instead of
    emitting a fresh one."""
    if not fulfiller_command(api):
        explain_no_fulfiller()
        return 1
    notes = "; ".join(filter(None, [f"level: {level}" if level else "", context or ""]))
    task_ref = initial_task_ref or emit_plan_task(goal, notes)
    if not drain_tasks(api, [task_ref]):
        return 1
    task = api.store.tasks.get(task_ref["id"])
    proposal = task.context.get("_applied") or {}
    _render_proposal(proposal)

    questions = proposal.get("refinement_questions") or []
    answers = []
    if questions:
        console.print("[bold]A few questions to sharpen this[/bold] [dim](enter to skip)[/dim]")
        for q in questions:
            reply = _input(f"  {q}\n  [bold cyan]›[/bold cyan] ").strip()
            if reply:
                answers.append(f"{q} -> {reply}")
    if answers:
        task_ref = emit_plan_task(goal, "; ".join(filter(None, [notes, *answers])))
        if drain_tasks(api, [task_ref]):
            task = api.store.tasks.get(task_ref["id"])
            proposal = task.context.get("_applied") or proposal
            _render_proposal(proposal)

    if not confirm("Create this campaign?"):
        console.print(f"[dim]Kept as a proposal — dojo campaign create --from-task {task.id}[/dim]")
        return 0
    result = materialize(task.id)
    console.print(f"[bold green]Campaign created:[/bold green] {result['id']} — "
                  "[bold]dojo daily[/bold] starts the first session.")
    if confirm("Start practicing now?"):
        return daily_flow(api)
    return 0


# ------------------------------------------------------------------
# Learn: goal → route → extend-or-fresh, one conversation
# ------------------------------------------------------------------

def learn_flow(api: DojoAPI, *, goal: str, plan_conversation) -> int:
    """Route-first "I want to learn X" (QUESTIONS 2026-07-09) at a TTY:
    routes the goal against the registry inline, asks the ONE consent
    question a near fit earns (extend, or start fresh?), and applies the
    choice — extend is deterministic (`learn_extend`); everything else falls
    into `plan_conversation(context=…, task_ref=…)`, the CLI-injected full
    plan → refine → create conversation."""
    if not fulfiller_command(api):
        explain_no_fulfiller()
        return 1
    res = api.learn(goal)
    if not drain_tasks(api, res["tasks"]):
        return 1
    task = api.store.tasks.get(res["tasks"][0]["id"])
    applied = task.context.get("_applied") or {}
    route = applied.get("route") or {}

    if route.get("action") in ("attach", "new_topic"):
        where = f"[cyan]{route['campaign']}[/cyan] › [cyan]{route['topic_path']}[/cyan]"
        console.print(f"\nThis looks like {where} [dim]({route.get('reason', '')})[/dim]")
        if confirm("  Extend that campaign?"):
            out = api.learn_extend(task.id)
            if out.get("already_covered") or out.get("already_applied"):
                console.print(f"  [green]✓[/green] {out['next']}")
            else:
                console.print(
                    f"  [green]✓ plan extended[/green] — phase {out['phase_appended']}: "
                    f"[cyan]{out['topic_path']}[/cyan] [dim](undo: {out['undo']})[/dim]"
                )
            return 0
        console.print("  [dim]starting fresh instead[/dim]")
        return plan_conversation(
            context=(
                f"the learner declined extending campaign {route['campaign']!r} — "
                "scope this as a separate campaign, not a duplicate of it"
            )
        )

    handoff = applied.get("handoff")
    if handoff:  # propose_campaign chained the plan task already
        console.print("[dim]No existing campaign fits — planning a new one…[/dim]")
        return plan_conversation(task_ref=handoff)
    console.print("[yellow]The route produced nothing actionable — try dojo learn --new.[/yellow]")
    return 1


# ------------------------------------------------------------------
# Capture → route → confirm, one breath
# ------------------------------------------------------------------

def capture_flow(api: DojoAPI, *, text: str, why: Optional[str],
                 locator: Optional[str] = None) -> int:
    """Capture → route → confirm in one breath: the text is durably saved
    FIRST (even with no fulfiller), the route task drains inline, and the
    proposal confirms with a keypress — declined or unroutable captures stay
    in the inbox."""
    res = api.capture(text, why=why, locator=locator)
    console.print(f"[green]✓ captured[/green] [dim]({res['capture_id']})[/dim]")
    if not fulfiller_command(api):
        console.print("[dim]An agent (or dojo task run) will propose where to file it.[/dim]")
        return 0
    if not drain_tasks(api, res["tasks"]):
        return 0
    cap = api.store.captures.get(res["capture_id"])
    proposal = cap.proposal or {}
    if cap.status == "filed":
        console.print(f"  filed under [cyan]{proposal.get('topic_path')}[/cyan] (autofile on)")
        return 0
    if proposal.get("action") in ("attach", "new_topic"):
        where = f"[cyan]{proposal['campaign']}[/cyan] › [cyan]{proposal['topic_path']}[/cyan]"
        if confirm(f"  File under {where}?"):
            api.inbox_confirm(cap.id)
            console.print("  [green]✓ filed — it can ground practice now[/green]")
        else:
            console.print(f"  [dim]kept in the inbox — dojo inbox to re-route or dismiss[/dim]")
    elif proposal.get("action") == "propose_campaign":
        if confirm(f"  Start a new campaign [cyan]{proposal.get('new_name')}[/cyan] for it?"):
            api.inbox_confirm(cap.id)
            console.print("  [green]✓ campaign created and note filed[/green]")
    else:
        console.print(f"  [yellow]stays in the inbox:[/yellow] {proposal.get('reason', '')}")
    return 0


def inbox_flow(api: DojoAPI) -> int:
    """Walks every waiting capture: confirm (file it), dismiss, or leave —
    unproposed captures just report that a route is still pending."""
    data = api.inbox()
    if not data["captures"]:
        console.print("[green]Inbox is empty.[/green]")
        return 0
    for cap in data["captures"]:
        prop = cap.get("proposal") or {}
        console.print(f"\n[bold]{cap['text']}[/bold] [dim]({cap['id']}, {cap['status']})[/dim]")
        if cap["status"] == "proposed" and prop.get("action") in ("attach", "new_topic"):
            if confirm(f"  → [cyan]{prop.get('campaign')}[/cyan] › [cyan]{prop.get('topic_path')}[/cyan]?"):
                api.inbox_confirm(cap["id"])
                console.print("  [green]✓ filed[/green]")
            elif confirm("  Dismiss it instead?", default=False):
                api.inbox_dismiss(cap["id"])
                console.print("  [dim]dismissed[/dim]")
        else:
            console.print("  [dim]awaiting a route — an agent or dojo task run will propose one[/dim]")
    return 0
