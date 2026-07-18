"""Human-facing interactive flows (owner directive 2026-07-08).

Two audiences, one core: agents get the JSON envelope protocol and are NEVER
blocked on input (cli._use_json guards every entry); humans at a TTY get flows
— AI tasks drain inline through the configured `fulfiller.command` with a
spinner, practice runs as one continuous loop, and proposals confirm with a
keypress. Everything here calls the same DojoAPI / task service the agent path
uses; this module renders and sequences, it never owns logic.
"""
from __future__ import annotations

import random
import shlex
import subprocess
import threading
import time
from typing import Any, Optional

try:  # line editing for every human prompt: arrows, ctrl-a/e, history.
    import readline  # noqa: F401  (importing is the feature)
except ImportError:  # some minimal builds ship without it — degrade quietly
    pass

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
    # Plain prompt through the BUILT-IN input(): readline then owns the prompt
    # boundary, so backspace can never eat the ›/question (owner field report
    # 2026-07-09). rich's console.input prints the prompt itself, which leaves
    # it erasable in most terminals.
    from rich.text import Text

    return input(Text.from_markup(prompt).plain)


def confirm(question: str, default: bool = True) -> bool:
    """Y/n keypress with a default; empty input takes the default.

    The suffixes are markup-ESCAPED: rich's tag regex starts lowercase, so
    un-escaped "[y/N]" was parsed as a tag and silently stripped — default-no
    prompts showed no options at all (owner field report 2026-07-17)."""
    suffix = r"\[Y/n]" if default else r"\[y/N]"
    answer = _input(f"{question} [bold]{suffix}[/bold] ").strip().lower()
    if not answer:
        return default
    return answer.startswith("y")


def fulfiller_command(api: DojoAPI) -> Optional[str]:
    """The configured one-string model command, or None. `model.command` is
    the user-facing key (owner ruling 2026-07-09: "fulfiller" is contract
    jargon, not people-speak); `fulfiller.command` stays honored for
    existing installs."""
    return (api.store.configs.get_value("model.command")
            or api.store.configs.get_value("fulfiller.command"))


def explain_no_fulfiller() -> None:
    """Tells the human their two options when an AI step has no model
    configured: drive dojo from an agent, or set `model.command` once."""
    console.print(
        "\n[yellow]This step needs an AI and no model is configured.[/yellow]\n"
        "Either drive dojo from your AI agent (it does the AI work itself), or\n"
        "point dojo at any model command once:\n"
        '  [bold]dojo config set model.command "codex exec"[/bold]   # or "ollama run llama3"\n'
    )


# Spinner phrases per task phase (owner ask 2026-07-09): one random pick per
# cycle from the bucket for what dojo is doing RIGHT NOW — flavor, not status;
# the honest label rides alongside.
PHASE_PHRASES: dict[str, list[str]] = {
    "campaign.plan": [
        "drawing the map…", "cutting scope like a ruthless editor…",
        "negotiating with your ambitions…", "finding the shortest path to competence…",
        "throwing out the boring chapters…",
    ],
    "exercise.generate": [
        "writing questions you'll pretend are easy…", "hiding the answers…",
        "sharpening the pointy ones…", "aiming at your weak spots (lovingly)…",
        "brewing fresh practice…",
    ],
    "exercise.diagnostic": [
        "sizing you up (gently)…", "asking around about you…",
        "calibrating the difficulty dial…", "figuring out what you already know…",
    ],
    "attempt.grade": [
        "sharpening the red pen…", "reading it twice to be fair…",
        "consulting the rubric gods…", "weighing every word you wrote…",
    ],
    "campaign.reflect": [
        "reading your mind (with receipts)…", "connecting the dots…",
        "updating its opinion of you…", "studying how you study…",
        "looking for patterns you'd rather hide…",
    ],
    "capture.route": [
        "finding this a home…", "checking the filing cabinet…",
        "sniffing out where this belongs…",
    ],
    "goal.route": [
        "checking if you already own this…", "looking for prior art in your head…",
        "seeing where this fits in your world…",
    ],
}


def _phrase_for(kind: str) -> str:
    bucket = PHASE_PHRASES.get(kind) or ["thinking…"]
    return random.choice(bucket)


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
        if task is None:
            # A just-emitted ref that doesn't resolve is store corruption, not
            # done-work: reporting success here turns into a crash downstream.
            console.print(f"  [red]✗ {ref['id']}: not found in the store — try dojo doctor[/red]")
            ok = False
            continue
        if task.status != "pending":
            continue
        label = task.kind.replace(".", " · ")

        # A rejected submission gets the task's full budget (max_submissions,
        # I5) before the flow gives up — a fresh sample usually clears a
        # validation miss (owner field report 2026-07-17: one rejection killed
        # the whole learn flow with two retries unspent, and no next step).
        while True:
            result: dict[str, Any] = {}

            def _run() -> None:
                try:
                    result["proc"] = subprocess.run(
                        shlex.split(command), input=task.prompt,
                        capture_output=True, text=True, timeout=timeout,
                    )
                except Exception as exc:  # timeout, missing binary, …
                    result["exc"] = exc

            worker = threading.Thread(target=_run, daemon=True)
            outcome = None
            with console.status(
                f"[cyan]{_phrase_for(task.kind)}[/cyan] [dim]({label})[/dim]",
                spinner="dots",
            ) as status:
                worker.start()
                while worker.is_alive():  # rotate the flavor while the model works
                    worker.join(timeout=4.0)
                    if worker.is_alive():
                        status.update(
                            f"[cyan]{_phrase_for(task.kind)}[/cyan] [dim]({label})[/dim]")
                try:
                    if "exc" in result:
                        raise result["exc"]
                    outcome = service.submit(api.store, task.id, result["proc"].stdout)
                except Exception as exc:
                    console.print(f"  [red]✗ {label} ({task.id}): {str(exc)[:120]}[/red]")
                    console.print(
                        "    [dim]nothing was submitted — check the model command "
                        "(dojo config get model.command), then re-run this command[/dim]")
                    ok = False
            if outcome is None or outcome.ok:
                break
            error = "; ".join(outcome.errors[:2])[:160]
            if outcome.status == "pending":  # budget remains — go again
                fresh = api.store.tasks.get(task.id)
                tries = f"{fresh.submissions}/{fresh.max_submissions}" if fresh else "?"
                console.print(f"  [yellow]✗ {label} rejected (try {tries}):[/yellow] "
                              f"[dim]{error}[/dim] — retrying")
                continue
            console.print(f"  [red]✗ {label} ({task.id}) failed: {error}[/red]")
            console.print(
                f"    [dim]what the model sent each try: dojo task show {task.id} --trace"
                " · re-running this command starts a fresh task[/dim]")
            ok = False
            break
    return ok


# ------------------------------------------------------------------
# Practice: one continuous session loop
# ------------------------------------------------------------------


class SessionRenderer:
    """Transcript mode — the default and the floor (append-only prints in
    the terminal's native scrollback: copyable, greppable, SSH/tmux-proof).
    Screen mode subclasses override PRESENTATION only; the session flow in
    practice_loop is identical in both, so the modes can never drift
    (display philosophy, owner-approved 2026-07-13)."""

    def header(self, done: int, total: int) -> None:
        """Prints the session banner with remaining count and commands."""
        console.print(f"\n[bold]Session[/bold] — {total - done} prompt(s) to go. "
                      "[dim](/why, /back [n], /skip too_easy|too_hard|forgot|bad_quality, /quit)[/dim]\n")

    def study_card(self, info: dict[str, Any], done: int, total: int) -> None:
        """Shows a ☆ presentation (prompt + material) as one panel."""
        console.print(Panel(
            f"{info['prompt']}\n\n[bold]{info['material']}[/bold]",
            title=f"[bold]{done} of {total}[/bold] · [cyan]☆ new material[/cyan]",
            border_style="cyan",
        ))

    def question(self, info: dict[str, Any], done: int, total: int) -> None:
        """Shows the current exercise prompt as a panel."""
        console.print(Panel(info["prompt"],
                            title=f"[bold]{done} of {total}[/bold]",
                            border_style="cyan"))

    def amend_review(self, prompt_text: str, current_answer: str, steps: int) -> None:
        """Shows the /back target: the earlier prompt and its current answer."""
        console.print(Panel(
            f"{prompt_text}\n\n[dim]your answer:[/dim] {current_answer}",
            title=f"[bold]← back {steps}[/bold]", border_style="yellow"))

    def note(self, markup: str) -> None:
        """Prints a one-line status/feedback message (rich markup)."""
        console.print(markup)

    def score(self, score: float, note: Optional[str]) -> None:
        """Prints a grade verdict line (✓/◐/✗ with the optional correction)."""
        _print_score(score, note)

    def ask(self, prompt: str) -> str:
        """Collects one line of learner input (tests patch _input beneath)."""
        return _input(prompt)

    def done(self) -> None:
        """Session over: settle/summary print in the normal buffer after this."""
        console.print("[bold green]Session complete.[/bold green]")


class ScreenRenderer(SessionRenderer):
    """Screen mode (opt-in: `dojo config set ui.mode screen` or `--screen`):
    each step clears and redraws — anchored progress header, a dim tail of
    what already happened, the current card. v1 is clear-redraw (no alt
    screen), so input works plainly and nothing can wedge the terminal;
    the history it scrolls away is DATA, not pixels — the session record
    and the store keep everything."""

    TAIL = 6

    def __init__(self) -> None:
        self._history: list[str] = []
        self._card: Optional[Panel] = None
        self._done = 0
        self._total = 0

    def _redraw(self) -> None:
        console.clear()
        console.print(f"[bold cyan]🥋 dojo session[/bold cyan] — "
                      f"[bold]{self._done} of {self._total}[/bold]  "
                      "[dim]/why · /back [n] · /skip <reason> · /quit[/dim]")
        for line in self._history[-self.TAIL:]:
            console.print(f"  [dim]{line}[/dim]")
        if self._card is not None:
            console.print(self._card)

    def header(self, done: int, total: int) -> None:
        """Records progress and redraws the screen."""
        self._done, self._total = done, total
        self._redraw()

    def study_card(self, info: dict[str, Any], done: int, total: int) -> None:
        """Makes the ☆ presentation the current card and redraws."""
        self._done, self._total = done, total
        self._card = Panel(
            f"{info['prompt']}\n\n[bold]{info['material']}[/bold]",
            title=f"[bold]{done} of {total}[/bold] · [cyan]☆ new material[/cyan]",
            border_style="cyan")
        self._redraw()

    def question(self, info: dict[str, Any], done: int, total: int) -> None:
        """Makes the exercise prompt the current card and redraws."""
        self._done, self._total = done, total
        self._card = Panel(info["prompt"], title=f"[bold]{done} of {total}[/bold]",
                           border_style="cyan")
        self._redraw()

    def amend_review(self, prompt_text: str, current_answer: str, steps: int) -> None:
        """Makes the /back target the current card and redraws."""
        self._card = Panel(
            f"{prompt_text}\n\n[dim]your answer:[/dim] {current_answer}",
            title=f"[bold]← back {steps}[/bold]", border_style="yellow")
        self._redraw()

    def ask(self, prompt: str) -> str:
        """Redraws before prompting, so re-asks (empty Enter, /why) replace
        the previous prompt line instead of stacking stray '›' lines
        (owner field report 2026-07-16)."""
        self._redraw()
        return _input(prompt)

    def note(self, markup: str) -> None:
        """Prints the message and folds it into the history tail — notes
        persist across redraws so the recent story stays visible."""
        from rich.text import Text

        self._history.append(Text.from_markup(markup.strip()).plain)
        console.print(markup)

    def score(self, score: float, note: Optional[str]) -> None:
        """Folds the verdict into the history tail, then prints it."""
        mark = "✓" if score >= 1.0 else ("◐" if score >= 0.7 else "✗")
        self._history.append(f"{mark} {score:.1f}" + (f" — {note}" if note else ""))
        _print_score(score, note)

    def done(self) -> None:
        """Final redraw without a card, then the completion line."""
        self._card = None
        self._redraw()
        console.print("[bold green]Session complete.[/bold green]")


def _session_renderer(api: DojoAPI, override: Optional[str] = None) -> SessionRenderer:
    """Resolves the display mode: explicit flag > `ui.mode` config >
    transcript (the default — trust before polish)."""
    mode = (override or api.store.configs.get_value("ui.mode", "") or "").strip()
    return ScreenRenderer() if mode == "screen" else SessionRenderer()


def practice_loop(api: DojoAPI, session: dict[str, Any],
                  r: Optional[SessionRenderer] = None) -> None:
    """Runs a session as one continuous conversation: reveal → answer →
    next, with `/skip <reason>` and `/quit` (pause; daily resumes). Free-form
    answers grade in ONE batch at the end (D1 — a model call between
    questions stalls the human), then a stats summary prints. All display
    goes through `r` (SessionRenderer) — one flow, two modes."""
    r = r or SessionRenderer()
    total = len(session["exercise_ids"])
    done = session.get("current_index", 0)
    r.header(done, total)
    # Free-form answers grade at the END, in one batch: a model call between
    # every question stalls the human's flow, and scores never gated
    # progression anyway (use-case audit D1).
    pending_grades: list[dict[str, Any]] = []
    while True:
        try:
            info = api.reveal_prompt(session_id=session["id"])
        except ValueError:
            break
        # Authoritative position, never a reveal count: a refused /back or an
        # amend re-reveals the SAME exercise (owner field report 2026-07-17:
        # the counter marched to "5 of 2" on one question).
        done = info["index"] + 1
        if info.get("present"):
            # Deliberate encoding event (ADR 017): show the material, plain
            # Enter confirms — the ONE place empty input is a real action
            # (nothing is answered, so nothing can be lost by accident).
            r.study_card(info, done, total)
            r.ask("[dim]read it, own it — Enter to continue[/dim] ")
            res = api.submit_answer(user_answer="", session_id=session["id"])
            r.note("  [cyan]✓ encoded — recall practice follows in coming sessions[/cyan]\n")
            if res.get("is_session_completed"):
                break
            continue
        r.question(info, done, total)
        answer = ""
        hinted = False
        while not answer.strip() or answer.strip() == "/why":
            if answer.strip() == "/why":
                # Curiosity strikes mid-question (owner field report
                # 2026-07-09): answer it inline, then keep waiting.
                reason = (session.get("packet_reasons") or {}).get(
                    info["exercise_id"], "(built before reasons were recorded)")
                r.note(f"  [dim]{reason}[/dim]")
                answer = ""
            got = r.ask("[bold cyan]›[/bold cyan] ")
            if not got.strip() and not hinted:
                # Empty input is never destructive (owner ruling) — but it
                # must never be SILENT either (owner field report 2026-07-16:
                # stacked mute '›' lines read as a broken multiline editor).
                r.note("  [dim]an empty line sends nothing — type an answer, "
                       "or /skip <reason>, /why, /quit[/dim]")
                hinted = True
            answer = got
        if answer.strip() in ("/quit", "/exit"):  # /exit: owner ask 2026-07-17
            r.note("[dim]Paused — dojo daily resumes right here.[/dim]")
            _settle_grades(api, pending_grades)
            return
        if answer.strip().startswith("/back"):
            # Amend an earlier answer (owner-approved supersede semantics):
            # /back reaches one question back, /back N reaches N. Only
            # pending grades amend; landed ones point at dojo correct.
            parts = answer.strip().split()
            steps = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
            # '/back' at the review chains one question further (owner field
            # report 2026-07-17: repeating /back cycled between the same two
            # questions — the review prompt read it as the new ANSWER).
            while True:
                peek = api.amend_previous_answer("", session_id=session["id"],
                                                 steps_back=steps, peek=True)
                if not peek.get("ok"):
                    hint = f" [dim]({peek['next']})[/dim]" if peek.get("next") else ""
                    r.note(f"  [yellow]{peek['error']}[/yellow]{hint}\n")
                    break
                r.amend_review(peek["prompt"], peek["current_answer"], steps)
                new_ans = r.ask("[bold yellow]new answer ('-' keeps it · '/back' "
                                "reaches further back) ›[/bold yellow] ").strip()
                if new_ans == "/back":
                    steps += 1
                    continue
                if new_ans.startswith("/"):
                    r.note("  [dim]commands don't amend — '-' keeps it, "
                           "'/back' goes further back[/dim]\n")
                    continue
                if new_ans and new_ans != "-":
                    amended = api.amend_previous_answer(
                        new_ans, session_id=session["id"], steps_back=steps)
                    if amended.get("ok"):
                        r.note("  [green]✓ amended — grades with the batch at the end[/green]\n")
                        for pg in pending_grades:
                            if pg.get("attempt_id") == amended["attempt_id"]:
                                pg["tasks"] = amended["tasks"]  # stale grade task superseded
                    else:
                        r.note(f"  [yellow]{amended['error']}[/yellow]\n")
                else:
                    r.note("  [dim]kept as it was[/dim]\n")
                break
            continue
        if answer.strip().startswith("/skip"):
            parts = answer.strip().split()
            reason = parts[1] if len(parts) > 1 else "forgot"
            res = api.skip_active_exercise(reason, session_id=session["id"])
            r.note(f"  [yellow]skipped ({reason})[/yellow]\n")
        elif answer.strip().startswith("/"):
            # An unrecognized command must never become an answer (owner field
            # report 2026-07-17: '/exit' was submitted and scored).
            r.note("  [yellow]unknown command[/yellow] [dim]— /why · /back \\[n] · "
                   "/skip <reason> · /quit[/dim]\n")
            continue
        else:
            res = api.submit_answer(user_answer=answer, session_id=session["id"])
            if res.get("not_an_answer"):
                # Calibration junk screen: nothing recorded — re-ask.
                r.note(f"  [yellow]that doesn't look like an answer[/yellow] "
                       f"[dim]— {res['next']}[/dim]\n")
                continue
            if res.get("pending_grade") and res.get("tasks"):
                pending_grades.append(res)
                r.note("  [dim]✓ recorded — scoring at the end[/dim]\n")
            elif res.get("diagnostic"):
                # Calibration measures, it doesn't grade — "correct" would be
                # a lie in both directions (owner directive 2026-07-17).
                r.note("  [cyan]✓ noted — calibration, not a test[/cyan]\n")
            else:
                correct = res.get("correct_answer")
                r.score(res["score"], None if res["score"] >= 1.0 else
                        (f"answer: {correct}" if correct else None))
        if res.get("is_session_completed"):
            break
    r.done()
    _settle_grades(api, pending_grades)
    _session_summary(api)


def _settle_grades(api: DojoAPI, pending: list[dict[str, Any]]) -> None:
    if not pending:
        return
    console.print(f"[bold]Scoring {len(pending)} answer(s)…[/bold]")
    drained = drain_tasks(api, [t for res in pending for t in res["tasks"]])
    for res in pending:
        attempt = api.store.attempts.get(res["campaign_id"], res["attempt_id"])
        if attempt.grader == "exposure":
            # ADR 017: first contact with never-encoded material (or a stated
            # knowledge gap) — no lapse, no accuracy hit; the reveal below IS
            # the teaching. Framed as news, not as a failure.
            console.print("  [cyan]☆ new to you — nothing scored against you[/cyan]")
            _reveal_answer(api, res)
        elif attempt.grader == "ai":
            _print_score(attempt.score, attempt.grade_feedback)
            if attempt.score == 0.0:
                # Total miss: feedback has nothing to correct against — show
                # the kernel itself (owner ruling: partial misses stay
                # feedback-only to keep noise down).
                _reveal_answer(api, res)
        else:
            console.print("  [yellow]grade still pending — an agent (or dojo task run) can finish it[/yellow]\n")
    if not drained:
        console.print("  [dim]dojo daily will re-surface unfinished grades tomorrow[/dim]")


def _reveal_answer(api: DojoAPI, res: dict[str, Any]) -> None:
    """Prints the stored model answer for a settled attempt's exercise —
    the re-encoding step after a total miss (ADR 017)."""
    ex = api.store.exercises.get(res["campaign_id"], res["exercise_id"])
    if ex is not None and ex.answer:
        console.print(f"  [bold]the answer:[/bold] {ex.answer}\n")


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
        label = c["name"] if len(c["name"]) <= 40 else c["name"][:39] + "…"
        table.add_row(label, ret, f"{c['due_now']}/{c['active_exercises']}", acc)
    console.print(table)
    console.print("  [dim]*estimated recall odds · dojo why explains today's picks[/dim]")


def daily_flow(api: DojoAPI, size: Optional[int] = None, reset: bool = False,
               mode: Optional[str] = None) -> int:
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
    for note in res.get("insight_notices", []):
        counts = " · ".join(f"{note[k]} {k}" for k in ("created", "updated", "resolved") if note.get(k))
        console.print(f"[yellow]Beliefs updated[/yellow] ([cyan]{note['campaign_id']}[/cyan]): "
                      f"{counts} — [bold]dojo insights[/bold] shows them, with receipts")
    for done in res.get("campaign_completions", []):
        console.print(f"[bold green]Campaign complete[/bold green] — {done['next']}")
    for idle in res.get("idle_campaigns", []):
        console.print(f"[dim]{idle['campaign_id']} untouched {idle['days_idle']:.0f}d — {idle['next']}[/dim]")
    for _ in range(2):  # at most: drain → rebuild → drain (cold-start diagnostic round)
        if res.get("session") is not None:
            break
        if res.get("status") == "complete_for_today":
            # Exact spec'd copy (QUESTIONS 2026-07-09): line 1 static, lesson
            # implicit, concession last; `dojo more` styled as a COMMAND.
            _print_done_for_today()
            if res.get("tasks"):
                drain_tasks(api, res["tasks"])  # tomorrow's replenishment, non-blocking
            return 0
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
    r = _session_renderer(api, mode)
    practice_loop(api, res["session"], r)
    if type(r) is SessionRenderer and not api.store.configs.get_value("ui.tip_screen_shown", ""):
        # One-time awareness (noise ruling: once, then never again).
        console.print("[dim]tip: prefer a full-screen session view? try it once: "
                      "dojo daily --screen · keep it: dojo config set ui.mode screen  "
                      "(shown once)[/dim]")
        api.save_config("ui.tip_screen_shown", "1")
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
        # A 0-accuracy phase is calibration: it measures, it never gates —
        # "@ 0%" would read as a bug, so say what it actually means.
        gate = (f"{crit['min_attempts']}+ attempts @ {crit['min_accuracy']:.0%}"
                if crit["min_accuracy"] else f"{crit['min_attempts']}+ attempts, no accuracy gate")
        lines.append(f"  Phase {p['phase']}: {', '.join(p['topics'])} "
                     f"[dim]({gate}"
                     + (f" — {p['focus']}" if p.get("focus") else "") + ")[/dim]")
    # The generated name is part of what the learner approves (STATE 7f).
    title = "Proposed campaign"
    if proposal.get("name"):
        title += f": {proposal['name']}"
    console.print(Panel("\n".join(lines), title=f"[bold green]{title}[/bold green]",
                        border_style="green"))


def plan_flow(api: DojoAPI, *, goal: str, level: Optional[str], context: Optional[str],
              emit_plan_task, materialize, initial_task_ref: Optional[dict] = None,
              mode: Optional[str] = None) -> int:
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
    if task is None:
        console.print(f"[red]✗ {task_ref['id']} vanished after fulfillment — try dojo doctor[/red]")
        return 1
    proposal = task.context.get("_applied") or {}
    _render_proposal(proposal)

    questions = proposal.get("refinement_questions") or []
    replies: list[Optional[str]] = [None] * len(questions)
    if questions:
        console.print("[bold]A few questions to sharpen this[/bold] "
                      "[dim]('-' skips one · '/back' revisits the previous)[/dim]")
        i = 0
        while i < len(questions):
            # Blank line + styled question: the previous free-form answer can
            # be long, and the next question must not read as its tail.
            console.print(f"\n  [bold cyan]?[/bold cyan] [bold]{questions[i]}[/bold]")
            if replies[i]:
                console.print(f"  [dim]previously: {replies[i]}[/dim]")
            # Empty input is never destructive (owner ruling 2026-07-09): an
            # accidental Enter re-asks; skipping is the deliberate '-'.
            while True:
                reply = _input("  [bold cyan]›[/bold cyan] ").strip()
                # Only '-' and '/back' are commands here; any other slash
                # token is a mistake, not an answer for the model.
                if reply in ("-", "/back") or (reply and not reply.startswith("/")):
                    break
                if reply:
                    console.print("  [dim]unknown command — '-' skips, '/back' "
                                  "revisits the previous question[/dim]")
                else:
                    console.print("  [dim]type an answer, '-' to skip, or '/back' "
                                  "to revisit the previous question[/dim]")
            if reply == "/back":
                # Control tokens never become answers (owner field report
                # 2026-07-17: '/back' was shipped to the model verbatim).
                if i == 0:
                    console.print("  [dim]this is the first question[/dim]")
                else:
                    i -= 1
                continue
            replies[i] = None if reply == "-" else reply
            i += 1
    answers = [f"{q} -> {r}" for q, r in zip(questions, replies) if r]
    if answers:
        task_ref = emit_plan_task(goal, "; ".join(filter(None, [notes, *answers])))
        if drain_tasks(api, [task_ref]):
            refreshed = api.store.tasks.get(task_ref["id"])
            if refreshed is not None:  # else: keep the first proposal — it was real
                task = refreshed
                proposal = task.context.get("_applied") or proposal
            _render_proposal(proposal)

    if not confirm("Create this campaign?"):
        console.print(f"[dim]Kept as a proposal — dojo campaign create --from-task {task.id}[/dim]")
        return 0
    result = materialize(task.id)
    created_name = (result.get("campaign") or {}).get("name") or result["id"]
    console.print(f"[bold green]Campaign created:[/bold green] {created_name}  "
                  f"[dim]({result['id']})[/dim]")
    if confirm("Start practicing it now?"):
        return first_session_flow(api, result["id"], mode=mode)
    console.print("[dim]When you're ready: dojo daily.[/dim]")
    return 0


def first_session_flow(api: DojoAPI, campaign_id: str, mode: Optional[str] = None) -> int:
    """The first practice right after creating a campaign practices THAT
    campaign — its calibration questions — never the general daily (owner
    field report 2026-07-13: "Start practicing now?" resumed an unrelated
    mid-flight session; the consent was about the new campaign). Any
    in-progress session is parked honestly: its unattempted exercises stay
    due and return through dojo daily."""
    if api.store.sessions.get_active() is not None:
        console.print("  [dim](pausing your other in-progress session — "
                      "its remaining prompts return via dojo daily)[/dim]")
    res = api.start_practice_session(campaign_id=campaign_id, reset=True)
    if res.get("session") is None:
        # A virgin campaign has no stock yet — the calibration questions are
        # a pending generation task. Drain inline, then start for real.
        if not drain_tasks(api, res.get("tasks") or []):
            return 1
        res = api.start_practice_session(campaign_id=campaign_id, reset=True)
    if res.get("session") is None:
        console.print("[yellow]Nothing to practice yet — fulfill the pending "
                      "task(s), then run dojo daily.[/yellow]")
        return 0
    practice_loop(api, res["session"], _session_renderer(api, mode))
    return 0


def _print_done_for_today() -> None:
    """The daily-completion message, exact spec'd copy (owner-ruled
    2026-07-09): no counters, no offers — a statement with the concession
    last. Line 1 is static; never varies."""
    console.print(
        "\n[bold green]✓ Done for today.[/bold green]\n"
        "Coming back tomorrow is what makes it stick.\n"
        "Go touch grass. 🌱  [dim](Genuinely still hungry? Run[/dim] "
        "[bold cyan]dojo more[/bold cyan] [dim]— it only says yes when your "
        "review budget agrees.)[/dim]"
    )


# ------------------------------------------------------------------
# More: the capacity channel, at the learner's request only
# ------------------------------------------------------------------

def more_flow(api: DojoAPI, *, force: bool = False, mode: Optional[str] = None) -> int:
    """The human `dojo more`: grants the bounded top-up and runs it as a
    normal practice loop, or relays the honest refusal with the 7-day
    projection and the debt-free alternative. One inline drain covers the
    no-stock → generation → re-ask round."""
    res = api.more(force=force)
    for _ in range(2):  # at most: generation → drain → re-ask
        if not res.get("extension_available"):
            console.print(f"[yellow]Not today:[/yellow] {res['reason']}")
            console.print(
                f"  [dim]{res['projected_due_7d']} review(s) due in the next 7 days · "
                f"capacity {res['capacity_7d']}[/dim]"
            )
            # Human surface: never point a person at the agent envelope
            # commands (owner field report 2026-07-17: "dojo ready" sent a
            # human into the machine-dialect prompt).
            console.print(f"  [dim]{res.get('alternative_interactive') or res['alternative']}[/dim]")
            return 0
        if res.get("session") is not None:
            break
        if not res.get("tasks") or not drain_tasks(api, res["tasks"]):
            for t in res.get("tasks", []):
                console.print(f"  pending: [cyan]{t['id']}[/cyan] — {t['submit_with']}")
            return 0
        res = api.more(force=force)
    if res.get("session") is None:
        console.print("[yellow]Nothing practicable came back — dojo stats shows the state.[/yellow]")
        return 0
    if res.get("warning"):
        console.print(f"[yellow]{res['warning']}[/yellow]")
    console.print(f"[bold]Extension granted[/bold] — {res['granted']} new item(s), "
                  "labeled so tomorrow's schedule stays honest.")
    practice_loop(api, res["session"], _session_renderer(api, mode))
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
