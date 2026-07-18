"""The `dojo` command-line interface.

One parser, two audiences (blueprint "two audiences, one guarantee"):
agents get JSON envelopes and are never blocked on interactive input
(`_use_json` triggers on --json, piped stdout, or --no-input); humans at a
TTY get the rich interactive flows from `dojo.interactive`. Every handler is
a thin wrapper: parse args, call `DojoAPI`, render. On success, `main` writes
one git recovery point per command (ADR 011).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
import shlex
import shutil
from pathlib import Path
from typing import Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .api import DojoAPI
from .logger import DEFAULT_DOJO_DIR
from .store import DojoStore, slugify
from .schemas import AttackPlanPhase, CriteriaEntry, Campaign, Candidate

console = Console()


def _use_json(args: argparse.Namespace) -> bool:
    """Agent path: explicit --json, piped output, or --no-input. The guarantee
    (owner directive 2026-07-08): this path NEVER blocks on interactive input;
    humans at a TTY get the interactive flows instead."""
    if getattr(args, "json", False):
        return True
    if getattr(args, "no_input", False):
        return True
    if not sys.stdout.isatty():
        return True
    return False


def _db_path(args: argparse.Namespace) -> Path | None:
    return Path(args.db) if getattr(args, "db", None) else None


def _print_json(value: Any) -> None:
    print(json.dumps(value, sort_keys=True))



def cmd_add(args: argparse.Namespace) -> int:
    """`dojo add`: ingest a file or --text as a Source; --generate also emits a grounded generation task (needs an unambiguous campaign or --topic)."""
    if args.path and args.text:
        raise SystemExit("provide either file path or --text, not both")
    if not args.path and not args.text:
        raise SystemExit("must provide either file path or --text")
    if args.text and not args.title:
        raise SystemExit("--title is required when adding raw --text")

    path_str = None
    if args.path:
        if args.path.startswith("http://") or args.path.startswith("https://"):
            raise SystemExit("Direct URL ingestion is not supported. Please add the webpage/transcript using --text and specify the original URL with --locator.")
        else:
            kind = "file"
            file_path = Path(args.path)
            if not file_path.exists():
                raise SystemExit(f"file not found: {args.path}")
            content = file_path.read_text(encoding="utf-8")
            title = args.title or file_path.name
            path_str = args.locator or str(file_path.resolve())
    else:
        kind = "text"
        content = args.text
        title = args.title
        path_str = args.locator

    api = DojoAPI(_db_path(args))
    output = api.add_source(
        title=title,
        content=content,
        kind=kind,
        path=path_str,
        mission=args.mission,
        generate_candidates=args.generate,
        topic=args.topic,
    )

    if _use_json(args):
        _print_json(output)
    else:
        console.print(f"[bold green]Successfully added source:[/bold green] [cyan]{output['source_id']}[/cyan] ({output['title']})")
        cand_count = output.get("candidates_count", 0)
        if cand_count > 0:
            console.print(f"  Generated [blue]{cand_count}[/blue] candidates.")
            console.print(f"  Next, run: [bold]dojo source review {output['source_id']}[/bold] to review them.")

    return 0


def cmd_source_list(args: argparse.Namespace) -> int:
    """`dojo source list`: all sources as a table or JSON."""
    api = DojoAPI(_db_path(args))
    sources = api.list_sources()
    if _use_json(args):
        _print_json(sources)
    else:
        if not sources:
            console.print("[yellow]No sources found.[/yellow] Add one using: [bold]dojo add[/bold]")
            return 0
        table = Table(title="Dojo Study Sources")
        table.add_column("ID", style="cyan")
        table.add_column("Title", style="green")
        table.add_column("Kind", style="magenta")
        table.add_column("Candidates", style="blue")
        table.add_column("Added At", style="dim")
        for s in sources:
            table.add_row(
                s["id"],
                s["title"],
                s["kind"],
                str(s.get("candidates_count", 0)),
                s["created_at"].split("T")[0],
            )
        console.print(table)
    return 0


def cmd_source_show(args: argparse.Namespace) -> int:
    """`dojo source show`: one source; --start-line/--end-line slice the content view."""
    api = DojoAPI(_db_path(args))
    source = api.get_source(args.name)
    if source is None:
        raise SystemExit(f"unknown source: {args.name}")
    if _use_json(args):
        _print_json(source)
    else:
        is_sliced = getattr(args, "start_line", None) is not None or getattr(args, "end_line", None) is not None
        if is_sliced:
            lines = source['content'].splitlines()
            start = (args.start_line - 1) if args.start_line is not None else 0
            end = args.end_line if args.end_line is not None else len(lines)
            content_display = "\n".join(lines[start:end])
            excerpt_label = f"Content Span (lines {getattr(args, 'start_line', None) or 1} to {getattr(args, 'end_line', None) or 'end'}):"
        else:
            content_display = source['content'][:300] + '...' if len(source['content']) > 300 else source['content']
            excerpt_label = "Content Excerpt:"

        details = (
            f"[bold cyan]ID:[/bold cyan] {source['id']}\n"
            f"[bold cyan]Kind:[/bold cyan] {source['kind']}\n"
            f"[bold cyan]Path/Locator:[/bold cyan] {source['path'] or 'N/A'}\n"
            f"[bold cyan]Mission:[/bold cyan] {source['mission'] or 'None'}\n"
            f"[bold cyan]Candidates Left:[/bold cyan] {source.get('candidates_count', 0)}\n"
            f"[bold cyan]Created At:[/bold cyan] {source['created_at']}\n\n"
            f"[bold cyan]{excerpt_label}[/bold cyan]\n"
            f"{content_display}"
        )
        panel = Panel(details, title=f"[bold green]Source: {source['title']}[/bold green]", expand=False)
        console.print(panel)
    return 0


def cmd_source_topics(args: argparse.Namespace) -> int:
    """`dojo source topics`: candidate counts per topic path."""
    api = DojoAPI(_db_path(args))
    try:
        output_data = api.get_source_topics(args.name)
    except ValueError as exc:
        raise SystemExit(str(exc))

    if _use_json(args):
        _print_json(output_data)
    else:
        if not output_data:
            console.print(f"[yellow]No candidates found for source {args.name}.[/yellow]")
            return 0

        table = Table(title=f"Proposed Topics for: {args.name}")
        table.add_column("Topic Path", style="cyan")
        table.add_column("Candidates Count", style="green")
        for t in output_data:
            count_val = t.get("count") or t.get("candidates_count", 0)
            table.add_row(t["topic_path"], str(count_val))
        console.print(table)
    return 0


def cmd_source_candidates(args: argparse.Namespace) -> int:
    """`dojo source candidates`: candidates awaiting review, optionally filtered by --topic."""
    api = DojoAPI(_db_path(args))
    try:
        output_data = api.get_source_candidates(args.name, topic_path=args.topic)
    except ValueError as exc:
        raise SystemExit(str(exc))

    if _use_json(args):
        _print_json(output_data)
    else:
        if not output_data:
            console.print(f"[yellow]No candidates found for source {args.name}[/yellow]")
            return 0

        table = Table(title=f"Candidates for: {args.name}")
        table.add_column("ID", style="cyan")
        table.add_column("Topic Path", style="magenta")
        table.add_column("Prompt", style="green")
        table.add_column("Answer/Rubric", style="blue")
        table.add_column("Diff", style="yellow")

        for c in output_data:
            ans_str = c.get("answer") or ""
            if not ans_str and c.get("rubric"):
                ans_str = json.dumps(c["rubric"])
            ans_short = ans_str[:40] + "..." if len(ans_str) > 40 else ans_str
            prompt_short = c["prompt"][:40] + "..." if len(c["prompt"]) > 40 else c["prompt"]
            table.add_row(
                c["id"],
                c["topic_path"],
                prompt_short,
                ans_short,
                c.get("difficulty") or "N/A",
            )
        console.print(table)
    return 0


def cmd_source_review(args: argparse.Namespace) -> int:
    """`dojo source review`: interactive accept/queue, reject, or $EDITOR-edit walk over candidates. TTY only — agents promote with `dojo queue`."""
    if _use_json(args) or getattr(args, "no_input", False):
        raise SystemExit("source review requires interactive terminal; use 'dojo queue' for non-blocking agent queueing")

    api = DojoAPI(_db_path(args))
    source = api.get_source(args.name)
    if source is None:
        raise SystemExit(f"unknown source: {args.name}")

    candidates = api.get_source_candidates(source["id"])
    if not candidates:
        console.print(f"[yellow]No candidates to review for source {source['id']}.[/yellow]")
        return 0

    console.print(f"[bold green]Starting interactive review for: {source['title']}[/bold green]")
    console.print(f"Reviewing {len(candidates)} candidates. Press Ctrl+C or 'q' to exit anytime.\n")

    idx = 0
    while idx < len(candidates):
        c = candidates[idx]
        c = api.get_candidate(c["id"])
        if not c:
            idx += 1
            continue

        card_text = (
            f"[bold cyan]Candidate ID:[/bold cyan] {c['id']}\n"
            f"[bold cyan]Topic Path:[/bold cyan] {c['topic_path']}\n"
            f"[bold cyan]Prompt:[/bold cyan] {c['prompt']}\n"
            f"[bold cyan]Answer:[/bold cyan] {c.get('answer') or 'N/A'}\n"
            f"[bold cyan]Rubric:[/bold cyan] {c.get('rubric') or 'None'}"
        )
        console.print(Panel(card_text, title=f"Review Candidate {idx + 1}/{len(candidates)}", expand=False))

        try:
            choice = input("Choice: [a]ccept & queue, [r]eject, [e]dit, [q]uit? [a]: ").strip().lower()
        except KeyboardInterrupt:
            console.print("\n[yellow]Review aborted.[/yellow]")
            break

        if choice == "q":
            break
        elif choice == "r":
            api.remove_candidate(c["id"])
            console.print("[red]Candidate rejected & removed.[/red]\n")
            idx += 1
        elif choice == "e":
            import tempfile, os, subprocess
            editor = os.environ.get("EDITOR", "nano")

            content_template = (
                f"Topic Path: {c['topic_path']}\n"
                f"Prompt: {c['prompt']}\n"
                f"Answer: {c.get('answer') or ''}\n"
            )

            with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w+", encoding="utf-8") as tf:
                tf.write(content_template)
                temp_name = tf.name

            try:
                subprocess.run([editor, temp_name], check=True)
                updated = Path(temp_name).read_text(encoding="utf-8")

                lines = updated.splitlines()
                new_topic = c["topic_path"]
                new_prompt = c["prompt"]
                new_answer = c.get("answer")

                for line in lines:
                    if line.startswith("Topic Path:"):
                        new_topic = line.split("Topic Path:", 1)[-1].strip()
                    elif line.startswith("Prompt:"):
                        new_prompt = line.split("Prompt:", 1)[-1].strip()
                    elif line.startswith("Answer:"):
                        new_answer = line.split("Answer:", 1)[-1].strip()

                api.save_candidate(
                    candidate_id=c["id"],
                    prompt=new_prompt,
                    topic_path=new_topic,
                    answer=new_answer,
                    rubric=c.get("rubric"),
                    difficulty=c.get("difficulty") or "intermediate",
                )
                console.print("[green]Candidate updated. Displaying card again:[/green]")
            except Exception as exc:
                console.print(f"[red]Failed to edit: {exc}[/red]")
            finally:
                if os.path.exists(temp_name):
                    os.unlink(temp_name)
        else:
            ex = api.promote_candidate(c["id"])
            console.print(f"[green]Candidate promoted to active exercise: {ex['id']}[/green]\n")
            idx += 1

    console.print("[bold green]Review session complete.[/bold green]")
    return 0


def cmd_queue(args: argparse.Namespace) -> int:
    """`dojo queue`: promote a candidate (cand_*) or a source topic's batch into active exercises."""
    api = DojoAPI(_db_path(args))
    promoted_exercises = []

    if args.item and args.item.startswith("cand_"):
        try:
            ex = api.promote_candidate(args.item)
            promoted_exercises.append(ex)
        except ValueError as exc:
            raise SystemExit(str(exc))
    elif args.source or (args.item and args.item.startswith("src_")):
        source_id = args.source or args.item
        try:
            res = api.promote_source_topic(source_id, topic_path=args.topic, limit=args.limit)
            promoted_exercises = res.get("exercises") or []
        except ValueError as exc:
            raise SystemExit(str(exc))
    else:
        raise SystemExit("must provide either candidate ID or --source ID to queue exercises")

    output = {
        "ok": True,
        "type": "candidates_queued",
        "data": {
            "promoted_count": len(promoted_exercises),
            "promoted_ids": [ex["id"] for ex in promoted_exercises],
        }
    }

    if _use_json(args):
        _print_json(output)
    else:
        if not promoted_exercises:
            console.print("[yellow]No candidates were promoted.[/yellow]")
        else:
            console.print(f"[bold green]Successfully promoted {len(promoted_exercises)} candidates into active exercises:[/bold green]")
            for ex in promoted_exercises:
                console.print(f"  - [cyan]{ex['id']}[/cyan] (Topic: [magenta]{ex['topic_path']}[/magenta]) -> Prompt: [italic]{ex['prompt']}[/italic]")
    return 0








def cmd_start(args: argparse.Namespace) -> int:
    """`dojo start`: start or resume a manual practice session; a thin queue emits generation tasks instead of blocking (I4)."""
    api = DojoAPI(_db_path(args))
    limit = args.limit if args.limit is not None else 5
    try:
        res = api.start_practice_session(topic=args.topic, limit=limit, reset=args.reset)
    except ValueError as exc:
        raise SystemExit(str(exc))

    is_new = res["is_new"]
    ps = res["session"]

    if ps is None:
        # No due exercises, but generation tasks were emitted (I4 honest floor).
        if _use_json(args):
            _print_json({
                "ok": True,
                "type": "tasks_pending",
                "tasks": res.get("tasks", []),
                "next": res.get("next"),
            })
        else:
            console.print("[yellow]No exercises are due yet.[/yellow]")
            for t in res.get("tasks", []):
                console.print(f"  Pending task [cyan]{t['id']}[/cyan] — {t['submit_with']}")
            console.print("  Fulfill the task(s), then run [bold]dojo start[/bold] again.")
        return 0

    if not is_new:
        if _use_json(args):
            _print_json({
                "ok": True,
                "type": "practice_session_resumed",
                "data": ps
            })
        else:
            console.print(f"[bold yellow]Resuming existing practice session:[/bold yellow] [cyan]{ps['id']}[/cyan]")
            console.print(f"  Exercises completed: {ps['current_index']}/{len(ps['exercise_ids'])}")
            console.print("  Run: [bold]dojo ready[/bold] or [bold]dojo reveal[/bold] to retrieve the next prompt.")
    else:
        if _use_json(args):
            _print_json({
                "ok": True,
                "type": "practice_session_started",
                "data": ps
            })
        else:
            console.print(f"[bold green]Successfully started practice session:[/bold green] [cyan]{ps['id']}[/cyan]")
            console.print(f"  Selected [blue]{len(ps['exercise_ids'])}[/blue] exercises in queue.")
            console.print("  Run: [bold]dojo ready[/bold] or [bold]dojo reveal[/bold] to reveal the first prompt.")
    return 0


def cmd_ready(args: argparse.Namespace) -> int:
    """`dojo ready` / `dojo reveal`: show the current exercise prompt and start the latency clock."""
    api = DojoAPI(_db_path(args))
    try:
        output_data = api.reveal_prompt(args.session)
    except ValueError as exc:
        msg = str(exc)
        if "no active practice session" in msg:
            msg = "no active practice session; start one with 'dojo start'"
        raise SystemExit(msg)

    if _use_json(args):
        _print_json(output_data)
    else:
        card_text = (
            f"[bold green]Session ID:[/bold green] [cyan]{output_data['session_id']}[/cyan]\n"
            f"[bold green]Exercise {output_data['index'] + 1}/{output_data['total']}:[/bold green] [cyan]{output_data['exercise_id']}[/cyan]\n"
            f"[bold green]Topic Path:[/bold green] [cyan]{output_data['topic_path']}[/cyan]\n"
            f"[bold green]Difficulty:[/bold green] [cyan]{output_data['difficulty'] or 'N/A'}[/cyan]\n\n"
            f"[bold green]Prompt:[/bold green]\n"
            f"[bold white]{output_data['prompt']}[/bold white]"
        )
        console.print(Panel(card_text, title="📝 [bold cyan]Practice Prompt[/bold cyan]", expand=False, border_style="cyan"))
        console.print("\n  Type your answer and run: [bold green]dojo answer \"your response\"[/bold green]\n")
    return 0


def cmd_answer(args: argparse.Namespace) -> int:
    """`dojo answer`: record an answer; exact/diagnostic scores render immediately, rubric answers emit a grade task."""
    api = DojoAPI(_db_path(args))
    try:
        output_data = api.submit_answer(args.response, args.session)
    except ValueError as exc:
        msg = str(exc)
        if "no active practice session" in msg:
            msg = "no active practice session; start one with 'dojo start'"
        elif "prompt not revealed yet" in msg:
            msg = "prompt not revealed yet; run 'dojo ready' to reveal it first"
        raise SystemExit(msg)

    if _use_json(args):
        _print_json(output_data)
    else:
        score = output_data["score"]
        if score == 1.0:
            result_str = "🎉 [bold green]CORRECT[/bold green]"
            border_style = "green"
            title = "✨ [bold green]Practice Results: Perfect![/bold green]"
        else:
            result_str = "❌ [bold red]INCORRECT[/bold red]"
            border_style = "red"
            title = "⚠️ [bold red]Practice Results: Keep Learning![/bold red]"

        feedback = (
            f"[bold green]Attempt ID:[/bold green] [cyan]{output_data['attempt_id']}[/cyan]\n"
            f"[bold green]Result:[/bold green] {result_str}\n"
            f"[bold green]Your Answer:[/bold green]\n[white]{output_data['user_answer']}[/white]\n\n"
            f"[bold green]Correct Answer / Rubric:[/bold green]\n[italic]{output_data['correct_answer'] or 'Rubric-graded'}[/italic]\n\n"
            f"[bold green]Latency:[/bold green] [dim]{output_data['latency_seconds']:.2f} seconds[/dim]\n\n"
        )
        if output_data["is_session_completed"]:
            feedback += "🎓 [bold green]Practice session completed![/bold green] Run [bold cyan]dojo progress[/bold cyan] to check your metrics."
        else:
            feedback += f"➡️ Run [bold cyan]dojo ready[/bold cyan] for the next exercise ({output_data['next_index'] + 1}/{output_data['total_exercises']})."

        console.print(Panel(feedback, title=title, expand=False, border_style=border_style))
    return 0


def cmd_progress(args: argparse.Namespace) -> int:
    """`dojo progress`: lifetime attempt aggregates plus the last 10 attempts."""
    api = DojoAPI(_db_path(args))
    output_data = api.get_progress()

    if output_data["total_attempts"] == 0:
        if _use_json(args):
            _print_json(output_data)
        else:
            console.print("[yellow]No practice attempts recorded yet.[/yellow] Queue some exercises and run [bold]dojo start[/bold].")
        return 0

    if _use_json(args):
        _print_json(output_data)
    else:
        total = output_data["total_attempts"]
        avg_score = output_data["average_score"]
        avg_latency = output_data["average_latency_seconds"]
        recent = output_data["recent_attempts"]

        stats = (
            f"[bold green]Total Practice Attempts:[/bold green] [white]{total}[/white]\n"
            f"[bold green]Average Accuracy:[/bold green] [cyan]{avg_score * 100:.1f}%[/cyan]\n"
            f"[bold green]Average Recall Latency:[/bold green] [cyan]{avg_latency:.2f} seconds[/cyan]\n"
        )
        console.print(Panel(stats, title="📈 [bold green]Dojo Practice Progress Summary[/bold green]", expand=False, border_style="green"))

        table = Table(title="📋 [bold cyan]Recent Practice Attempts (Last 10)[/bold cyan]", border_style="cyan")
        table.add_column("Date", style="dim")
        table.add_column("Exercise ID", style="cyan")
        table.add_column("Prompt Excerpt", style="green")
        table.add_column("Score", style="magenta")
        table.add_column("Latency", style="yellow")

        for a in recent:
            prompt_short = a["prompt"][:40] + "..." if len(a["prompt"]) > 40 else a["prompt"]
            table.add_row(
                a["created_at"].split("T")[0],
                a["exercise"].split("/")[-1].replace(".md", "") if "/" in a["exercise"] else a["exercise"],
                prompt_short,
                f"{a['score'] * 100:.0f}%",
                f"{a['latency_seconds']:.1f}s",
            )
        console.print(table)
    return 0


def _is_owned_by_dojo(target_path: Path) -> bool:
    skill_md = target_path / "SKILL.md"
    if skill_md.exists() and skill_md.is_file():
        try:
            content = skill_md.read_text(encoding="utf-8")
            if content.startswith("---"):
                end_idx = content.find("---", 3)
                if end_idx != -1:
                    frontmatter = content[3:end_idx]
                    for line in frontmatter.splitlines():
                        line = line.strip()
                        if ":" in line:
                            key, val = line.split(":", 1)
                            k = key.strip()
                            v = val.strip().strip('"').strip("'")
                            if k == "owner" and v == "github.com/Stan15/dojo":
                                return True
        except Exception:
            pass
    return False


def cmd_install(args: argparse.Namespace) -> int:
    """`dojo install`: copy the packaged SKILL into an agent's skills directory (doctor-gated; ownership-checked unless --force; --argv records a fulfiller command)."""
    store = DojoStore(_db_path(args))
    results = store.doctor.run()
    all_errors = [err for errs in results.values() for err in errs]
    if all_errors and not getattr(args, "force", False):
        if _use_json(args):
            _print_json({
                "ok": False,
                "error": "Dojo repository validation failed",
                "errors": all_errors
            })
            raise SystemExit(1)
        else:
            console.print("[bold red]✗ Dojo Doctor found issues in your repository:[/bold red]")
            for err in all_errors:
                console.print(f"  [red]✗[/red] {err}")
            console.print("[yellow]To bypass this check, run install with --force.[/yellow]")
            raise SystemExit(1)

    agent = args.agent
    dest = getattr(args, "dest", None)

    if not agent and not dest:
        if _use_json(args) or getattr(args, "no_input", False) or not sys.stdout.isatty():
            raise SystemExit("must specify agent name or --dest path in non-interactive mode")

        console.print("[bold cyan]Please select the target agent to install the Dojo skill into:[/bold cyan]")
        console.print("  [1] [bold]Hermes[/bold] (~/.hermes/skills/dojo)")
        console.print("  [2] [bold]OpenClaw[/bold] (~/.openclaw/skills/dojo)")
        console.print("  [3] [bold]Other Agent / Custom Path[/bold]")
        console.print("  [q] Quit")

        try:
            choice = input("\nSelect an option [1-3, q]: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Installation cancelled.[/yellow]")
            return 1

        if choice == "1":
            agent = "hermes"
        elif choice == "2":
            agent = "openclaw"
        elif choice == "3":
            try:
                agent = input("Enter agent name (e.g. claude-code): ").strip()
                if not agent:
                    agent = "custom"
                default_dest = Path.home() / f".{agent}" / "skills" / "dojo"
                dest_input = input(f"Enter installation destination directory [{default_dest}]: ").strip()
                if dest_input:
                    dest = dest_input
            except (KeyboardInterrupt, EOFError):
                console.print("\n[yellow]Installation cancelled.[/yellow]")
                return 1
        else:
            console.print("[yellow]Cancelled.[/yellow]")
            return 0

    home = Path.home()
    if dest:
        target_path = Path(dest)
        if not agent:
            agent = "custom"
    else:
        if agent == "hermes":
            target_path = home / ".hermes" / "skills" / "dojo"
        elif agent == "openclaw":
            target_path = home / ".openclaw" / "skills" / "dojo"
        else:
            target_path = home / f".{agent}" / "skills" / "dojo"

    # The skill ships as package data — installs must never depend on a repo
    # checkout (owner-reported: `dojo install codex` failed from a venv install).
    if hasattr(sys, "_MEIPASS"):
        repo_skills_dojo = Path(getattr(sys, "_MEIPASS")) / "dojo" / "skills" / "dojo"
    else:
        repo_skills_dojo = Path(__file__).resolve().parent / "skills" / "dojo"

    if not (repo_skills_dojo / "SKILL.md").exists():
        raise SystemExit(f"error: packaged skill not found at {repo_skills_dojo} (broken install?)")

    force = getattr(args, "force", False)
    if target_path.exists() and not force:
        if not _is_owned_by_dojo(target_path):
            raise SystemExit(
                f"error: target directory '{target_path}' exists but does not appear to be "
                f"owned by Dojo (missing 'owner: github.com/Stan15/dojo' signature in SKILL.md frontmatter). "
                f"To prevent overwriting other agent skills, please rename or delete it manually, "
                f"or run with --force to overwrite."
            )

    try:
        if target_path.exists():
            if target_path.is_dir():
                shutil.rmtree(target_path)
            else:
                target_path.unlink()

        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            repo_skills_dojo, target_path,
            ignore=shutil.ignore_patterns("__init__.py", "__pycache__", "*.pyc"),
        )
    except Exception as exc:
        raise SystemExit(f"error: failed to install dojo skill to {target_path}: {exc}")

    store = DojoStore(_db_path(args))

    # Harness agents need nothing beyond the skill: they fulfill tasks
    # themselves (ADR 010). An optional one-string fulfiller command enables
    # headless use (dojo task run) — no wrapper scripts, ever (Q1).
    fulfiller = getattr(args, "argv", None)
    if fulfiller:
        store.configs.set("model.command", fulfiller)

    output = {
        "ok": True,
        "type": "skill_installed",
        "data": {
            "agent": agent,
            "path": str(target_path.resolve()),
            "fulfiller_command": fulfiller,
        },
        "next": "the agent can now drive dojo via the skill; tasks it sees in envelopes "
                "are fulfilled inline and submitted with `dojo task submit <id>`",
    }

    if _use_json(args):
        _print_json(output)
    else:
        console.print(f"[bold green]Successfully installed dojo skill for {agent}![/bold green]")
        console.print(f"  Destination: [cyan]{target_path}[/cyan]")
        if fulfiller:
            console.print(f"  Headless fulfiller: [italic]{fulfiller}[/italic] (drives `dojo task run`)")

    return 0


# Doctor categories that are ADVISORY: real findings, but recoverable states a
# running system produces normally (e.g. a store awaiting its per-command audit
# commit — the owner was mid-`dojo learn` when install.sh's doctor gate read a
# dirty tree as non-compliance and ROLLED BACK the install, 2026-07-09). Only
# structural non-compliance may gate installs / exit non-zero.
_DOCTOR_ADVISORY_CATEGORIES = frozenset({"Version control audit"})


def cmd_doctor(args: argparse.Namespace) -> int:
    """`dojo doctor`: run every store health check; exit 1 only on structural
    findings — advisory categories report but never fail the command."""
    store = DojoStore(_db_path(args))

    # ADR 018: doctor is the one-pass layout migrator — legacy campaigns
    # (journal/plan/topics in frontmatter, changelog.md) re-save into the
    # vault layout. Idempotent; counted honestly below.
    migrated = store.campaigns.migrate_layout()

    results = store.doctor.run()

    structural = [err for cat, errs in results.items()
                  if cat not in _DOCTOR_ADVISORY_CATEGORIES for err in errs]
    advisories = [err for cat in _DOCTOR_ADVISORY_CATEGORIES
                  for err in results.get(cat, [])]

    if _use_json(args):
        _print_json({
            "ok": len(structural) == 0,
            "results": results,
            "errors": structural,
            **({"advisories": advisories} if advisories else {}),
            **({"migrated_campaigns": migrated} if migrated else {}),
        })
    else:
        console.print("[bold cyan]Dojo Doctor Diagnostics[/bold cyan]")
        console.print("=======================")
        if migrated:
            console.print(f"[cyan]↻ migrated {migrated} campaign(s) to the vault layout (ADR 018)[/cyan]")
        for category, errors in results.items():
            if not errors:
                console.print(f"[green]✓[/green] [bold]{category}[/bold]")
            elif category in _DOCTOR_ADVISORY_CATEGORIES:
                console.print(f"[yellow]⚠[/yellow] [bold]{category}[/bold]")
                for err in errors:
                    console.print(f"    - [yellow]{err}[/yellow]")
            else:
                console.print(f"[red]✗[/red] [bold]{category}[/bold]")
                for err in errors:
                    console.print(f"    - [red]{err}[/red]")
        console.print("")

        if structural:
            console.print(f"[bold red]✗ Dojo Doctor found {len(structural)} issues in your repository.[/bold red]")
        elif advisories:
            console.print(f"[bold yellow]⚠ Healthy, with {len(advisories)} advisory note(s) — nothing blocking.[/bold yellow]")
        else:
            if not store.dojo_dir.exists():
                console.print("[bold green]✓ Dojo Doctor: Repository directory does not exist yet (will be initialized on first run). Folder is clear![/bold green]")
            else:
                console.print("[bold green]✓ Dojo Doctor: Repository directory is completely compliant and clean![/bold green]")

    return 1 if structural else 0


def cmd_due(args: argparse.Namespace) -> int:
    """`dojo due`: count of unattempted active exercises, optionally under a topic prefix."""
    api = DojoAPI(_db_path(args))
    count = api.get_due_count(topic=args.topic)
    if _use_json(args):
        _print_json({"due_count": count})
    else:
        console.print(f"You have [bold cyan]{count}[/bold cyan] exercises due.")
    return 0


def cmd_skip(args: argparse.Namespace) -> int:
    """`dojo skip`: skip the current exercise with a reason — calibration evidence, not failure."""
    api = DojoAPI(_db_path(args))
    try:
        res = api.skip_active_exercise(reason=args.reason, feedback=args.feedback, session_id=args.session)
    except ValueError as exc:
        raise SystemExit(str(exc))

    if _use_json(args):
        _print_json(res)
    else:
        feedback_text = (
            f"[bold cyan]Skipped Exercise:[/bold cyan] {res['exercise_id']}\n"
            f"[bold cyan]Reason:[/bold cyan] {res.get('skip_reason') or args.reason}\n"
        )
        if res.get('feedback'):
            feedback_text += f"[bold cyan]Feedback:[/bold cyan] {res['feedback']}\n"
        feedback_text += "\n"
        if res["is_session_completed"]:
            feedback_text += "[bold green]Practice session completed![/bold green] Run 'dojo progress' to check your metrics."
        else:
            feedback_text += f"Run [bold]dojo ready[/bold] for the next exercise ({res['next_index'] + 1}/{res['total_exercises']})."
        console.print(Panel(feedback_text, title="Exercise Skipped", expand=False))
    return 0


def cmd_correct(args: argparse.Namespace) -> int:
    """`dojo correct`: human override of the last attempt's score (highest grading authority)."""
    api = DojoAPI(_db_path(args))
    try:
        res = api.correct_last_attempt(score=args.score, feedback=args.feedback)
    except ValueError as exc:
        raise SystemExit(str(exc))

    if _use_json(args):
        _print_json(res)
    else:
        feedback_text = (
            f"[bold cyan]Corrected Attempt ID:[/bold cyan] {res['id']}\n"
            f"[bold cyan]Exercise ID:[/bold cyan] {res.get('exercise', 'N/A')}\n"
            f"[bold cyan]New Score:[/bold cyan] [bold green]{res['score']}[/bold green] (Override)\n"
        )
        if res.get('feedback'):
            feedback_text += f"[bold cyan]Feedback/Note:[/bold cyan] {res['feedback']}\n"
        console.print(Panel(feedback_text, title="Attempt Corrected", expand=False))
    return 0


def cmd_admin_consolidate(args: argparse.Namespace) -> int:
    """`dojo reflect` / `dojo admin consolidate`: emit reflection tasks for campaigns holding unreflected evidence."""
    api = DojoAPI(_db_path(args))
    try:
        res = api.consolidate_learner_profile(campaign_id=args.campaign)
    except ValueError as exc:
        raise SystemExit(str(exc))

    if _use_json(args):
        _print_json(res)
    else:
        console.print("[bold green]Profile consolidation completed successfully.[/bold green]")
        if "campaigns" in res:
            for campaign_res in res["campaigns"]:
                campaign_id = campaign_res.get("campaign_id")
                status = campaign_res.get("status")
                if status == "skipped":
                    console.print(f"\n[bold yellow]Campaign {campaign_id}: skipped[/bold yellow] (no new attempts or active feedback)")
                elif status == "ok":
                    console.print(f"\n[bold green]Campaign {campaign_id}: consolidated[/bold green]")
                    if campaign_res.get("hypotheses"):
                        table = Table()
                        table.add_column("Key", style="cyan")
                        table.add_column("Description", style="green")
                        table.add_column("Status", style="magenta")
                        for h in campaign_res["hypotheses"]:
                            table.add_row(h["key"], h["description"], h.get("status", "active"))
                        console.print(table)
                    else:
                         console.print("No active learner hypotheses/misconceptions identified.")
        else:
            status = res.get("status")
            campaign_id = res.get("campaign_id")
            if status == "skipped":
                console.print(f"\n[bold yellow]Campaign {campaign_id}: skipped[/bold yellow] (no new attempts or active feedback)")
            elif status == "ok":
                if res.get("hypotheses"):
                    console.print(f"\n[bold]Consolidated Active Hypotheses for Campaign {campaign_id}:[/bold]")
                    table = Table()
                    table.add_column("Key", style="cyan")
                    table.add_column("Description", style="green")
                    table.add_column("Status", style="magenta")
                    for h in res["hypotheses"]:
                        table.add_row(h["key"], h["description"], h.get("status", "active"))
                    console.print(table)
                else:
                    console.print(f"No active learner hypotheses/misconceptions identified for Campaign {campaign_id}.")
    return 0



def cmd_feedback(args: argparse.Namespace) -> int:
    """`dojo feedback`: store the learner's comment verbatim as a feedback insight for the next reflection."""
    api = DojoAPI(_db_path(args))
    try:
        res = api.add_learner_feedback(
            comment=args.comment,
            campaign_id=args.campaign,
        )
    except ValueError as exc:
        raise SystemExit(str(exc))

    if _use_json(args):
        _print_json(res)
    else:
        feedback_text = (
            f"[bold green]Learner feedback saved successfully![/bold green]\n"
            f"[bold cyan]ID:[/bold cyan] {res['id']}\n"
            f"[bold cyan]Key:[/bold cyan] {res['key']}\n"
            f"[bold cyan]Topic Path:[/bold cyan] {res.get('topic_path') or 'None'}\n"
            f"[bold cyan]Content:[/bold cyan] {res['description']}\n"
        )
        console.print(Panel(feedback_text, title="Feedback Logged", expand=False))
    return 0


def cmd_config_set(args: argparse.Namespace) -> int:
    """`dojo config set`: write one config key to the store's config.yaml."""
    api = DojoAPI(_db_path(args))
    res = api.save_config(args.key, args.value)
    if _use_json(args):
        _print_json(res)
    else:
        console.print(f"[bold green]Config set successfully:[/bold green] [cyan]{args.key}[/cyan] = [green]{args.value}[/green]")
    return 0


def cmd_config_show(args: argparse.Namespace) -> int:
    """`dojo config show`: every configured key/value."""
    api = DojoAPI(_db_path(args))
    configs = api.list_configs()
    if _use_json(args):
        _print_json(configs)
    else:
        if not configs:
            console.print("[yellow]No configuration preferences set yet.[/yellow]")
            return 0
        table = Table(title="Dojo Learner Configuration Preferences")
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="green")
        for k, v in sorted(configs.items()):
            table.add_row(k, v)
        console.print(table)
    return 0


def _emit_plan_task(store, goal: str, context_notes: str) -> dict[str, Any]:
    from .tasks import flows

    task = flows.request_plan(
        store, goal=goal, context_notes=context_notes,
        existing_topics=flows.registry_topic_paths(store),
    )
    return flows.task_ref(task)


def cmd_campaign_plan(args: argparse.Namespace) -> int:
    """Emits a campaign.plan task (ADR 010). The fulfilled task carries the
    proposal (mission/topics/phases/refinement questions); materialize it with:
    dojo campaign create --from-task <task-id>."""
    from .store import DojoStore
    from .tasks import flows

    store = DojoStore(_db_path(args))
    if not _use_json(args):
        from .api import DojoAPI as _API
        from .interactive import plan_flow

        api = _API(_db_path(args))
        return plan_flow(
            api, goal=args.goal, level=getattr(args, "level", None),
            context=getattr(args, "context", None),
            emit_plan_task=lambda goal, notes: _emit_plan_task(api.store, goal, notes),
            materialize=lambda task_id: _materialize_core(api, task_id, None),
            mode=_display_mode(args),
        )
    notes = []
    if getattr(args, "level", None):
        notes.append(f"level: {args.level}")
    if getattr(args, "context", None):
        notes.append(args.context)
    task_ref_ = _emit_plan_task(store, args.goal, "; ".join(notes))
    tid = task_ref_["id"]
    _print_json({
        "ok": True,
        "task": task_ref_,
        "next": (
            f"fulfill the task (dojo task show {tid} --prompt → produce the JSON → "
            f"dojo task submit {tid}); review the proposal and its refinement_questions "
            f"with the learner, then: dojo campaign create --from-task {tid} "
            f"[--name <override>]"
        ),
    })
    return 0


def _materialize_core(api: DojoAPI, task_id: str, name: str | None,
                      into: str | None = None) -> dict[str, Any]:
    """Deterministic creation from a fulfilled campaign.plan task (I2:
    review-before-trust — the human said yes before this runs). Shared by the
    agent envelope path and the interactive flow. `into` initializes a BARE
    campaign (capture-born, Q 6g) with the proposal instead of creating a new
    one; campaigns that already have a plan refuse — established plans change
    only through reflection + change authority."""
    task = api.store.tasks.get(task_id)
    if task is None or task.kind != "campaign.plan":
        raise SystemExit(f"error: {task_id} is not a campaign.plan task")
    if task.status != "fulfilled":
        raise SystemExit(f"error: task {task_id} is {task.status}, not fulfilled")
    proposal = (task.context or {}).get("_applied")
    if not proposal:
        raise SystemExit(f"error: task {task_id} carries no applied proposal")

    if into:
        return _materialize_into(api, into, proposal)

    topic_paths = [t["path"] for t in proposal["topics"]]
    root = topic_paths[0].split(".")[0] if topic_paths else "general"
    # The AI-generated label leads (owner directive 2026-07-15: the raw goal
    # as a name/id was the bug — camp_i-have-terrible-memory); the goal
    # stays verbatim in the task context and the mission carries the intent.
    name = name or proposal.get("name") or task.context.get("goal") or root

    res = api.create_campaign(
        name=name,
        topic_path=root,
        mission=proposal["mission"],
    )
    campaign = api.store.campaigns.get(res["id"])
    campaign.attack_plan = [AttackPlanPhase.model_validate(p) for p in proposal["phases"]]
    # Phase 1 of a fresh plan is calibration, so the campaign starts in
    # diagnostic mode — same stamp the direct-create door sets (owner field
    # report 2026-07-17: without it, the first practice generated ungated
    # practice items that landed as invisible candidates). Advancement past
    # phase 1 clears it.
    campaign.strategy_profile = {**campaign.strategy_profile, "mode": "diagnostic"}
    # Topic kinds (recall vs skill) ride along for the M3 scheduler.
    campaign.topics = proposal["topics"]
    lines = [f"# {name}", "", proposal["mission"], ""]
    for t in proposal["topics"]:
        lines.append(f"- `{t['path']}` ({t['kind']}): {t.get('summary', '')}")
    campaign.syllabus_markdown = "\n".join(lines)
    # The learner just said yes to THIS plan — record it as the confirmed
    # baseline change authority measures future revisions against.
    from datetime import datetime, timezone
    from .tasks import authority

    campaign.pedagogical_journal.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": authority.PLAN_CONFIRMED,
        "trigger": "campaign create --from-task (learner approved the proposal)",
        "hypothesis": "initial plan confirmed at creation",
        "status": "applied",
        "plan_snapshot": [p.model_dump() for p in campaign.attack_plan],
    })
    api.store.campaigns.save(campaign)
    return {
        "campaign": api.store.campaigns.get(res["id"]).model_dump(),
        "id": res["id"],
        "refinement_questions": proposal.get("refinement_questions", []),
    }


def _materialize_into(api: DojoAPI, campaign_id: str, proposal: dict[str, Any]) -> dict[str, Any]:
    """Applies a fulfilled plan proposal ONTO an existing bare campaign: the
    consent step for capture-born campaigns (the learner reviewed the plan
    and named the target). Initialization only — a non-empty attack_plan
    means the campaign is established and refuses."""
    from datetime import datetime, timezone
    from .tasks import authority

    campaign = api.store.campaigns.get(campaign_id)
    if campaign is None:
        raise SystemExit(f"error: campaign {campaign_id!r} not found")
    if campaign.attack_plan:
        raise SystemExit(
            f"error: {campaign_id} already has a plan — plan changes go through "
            "reflection and dojo plan confirm, never --into"
        )
    campaign.mission = proposal["mission"]
    known = {t.get("path") for t in campaign.topics}
    campaign.topics.extend(t for t in proposal["topics"] if t["path"] not in known)
    campaign.attack_plan = [AttackPlanPhase.model_validate(p) for p in proposal["phases"]]
    campaign.strategy_profile = {**campaign.strategy_profile, "mode": "diagnostic"}
    lines = [f"# {campaign.name}", "", proposal["mission"], ""]
    for t in proposal["topics"]:
        lines.append(f"- `{t['path']}` ({t['kind']}): {t.get('summary', '')}")
    campaign.syllabus_markdown = "\n".join(lines)
    campaign.pedagogical_journal.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": authority.PLAN_CONFIRMED,
        "trigger": "campaign create --from-task --into (learner approved the plan for this campaign)",
        "hypothesis": "initial plan confirmed for a capture-born campaign",
        "status": "applied",
        "plan_snapshot": [p.model_dump() for p in campaign.attack_plan],
    })
    api.store.campaigns.save(campaign)
    return {
        "campaign": api.store.campaigns.get(campaign_id).model_dump(),
        "id": campaign_id,
        "refinement_questions": proposal.get("refinement_questions", []),
    }


def _materialize_campaign_from_task(args: argparse.Namespace) -> int:
    api = DojoAPI(_db_path(args))
    result = _materialize_core(api, args.from_task, getattr(args, "name", None),
                               into=getattr(args, "into", None))
    _print_json({
        "ok": True,
        "type": "campaign_created",
        "data": result["campaign"],
        "refinement_questions": result["refinement_questions"],
        "next": "run dojo daily to begin practicing",
    })
    return 0


def cmd_campaign_create(args: argparse.Namespace) -> int:
    """`dojo campaign create`: materialize a fulfilled plan task (--from-task), or create directly — at a TTY this runs the diagnostic onboarding conversation; failures/cancel clean up the partial campaign."""
    if getattr(args, "from_task", None):
        return _materialize_campaign_from_task(args)
    api = DojoAPI(_db_path(args))

    if not _use_json(args):
        console.print("[bold green]Initializing learning campaign...[/bold green]")

    source_id = None
    try:
        # 1. Ingest source if provided
        if getattr(args, "source", None):
            if not _use_json(args):
                console.print(f"[bold green]Ingesting and attaching source: [cyan]{args.source}[/cyan]...[/bold green]")
            path = args.source
            path_str = None
            if path.startswith("http://") or path.startswith("https://"):
                kind = "url"
                path_str = path
                title = Path(path).name or path
                content = f"Content of URL: {path}"
            else:
                file_path = Path(path)
                if file_path.exists():
                    kind = "file"
                    content = file_path.read_text(encoding="utf-8")
                    title = file_path.name
                    path_str = str(file_path.resolve())
                else:
                    kind = "text"
                    content = path
                    title = f"Goal Context: {args.goal[:20]}..."
                    path_str = None

            source_res = api.add_source(
                title=title,
                content=content,
                kind=kind,
                path=path_str,
                mission=f"Grounded material for campaign: {args.goal}"
            )
            source_id = source_res["source_id"]

        # 2. Derive topic path — a SINGLE-segment root (OP #17: dotting the
        # goal's words minted a 5-level root from a 5-word goal, past the
        # depth cap, making every later new_topic leaf off it unroutable).
        words = "".join(c for c in args.goal.lower() if c.isalnum() or c == " ").split()
        temp_slug = "_".join(words[:3])[:25].rstrip("_")
        if not temp_slug:
            temp_slug = f"topic_{uuid.uuid4().hex[:8]}"

        # 3. Create campaign — labels stay short (owner directive 2026-07-15:
        # the raw goal as a name/id is the bug). With no AI in the loop at this
        # door, the fallback is mechanical: the goal's first few words, same
        # cap as AI-generated labels; the full goal stays verbatim in mission.
        from . import limits as _limits
        fallback_label = " ".join(args.goal.split()[: _limits.ROUTE_NEW_NAME_WORDS])
        res = api.create_campaign(
            name=args.name or fallback_label or "New Campaign",
            topic_path=temp_slug,
            mission=args.goal,
            source_id=source_id
        )
        campaign_id = res["id"]

        # 4. Overwrite to set default diagnostic configuration
        campaign = api.store.campaigns.get(campaign_id)
        if campaign:
            campaign.strategy_profile = {
                "mode": "diagnostic",
                "difficulty": args.level,
                "scaffolding": "high" if args.level == "beginner" else ("medium" if args.level == "intermediate" else "low")
            }
            campaign.attack_plan = [
                AttackPlanPhase(
                    phase=0,
                    topics=[f"{temp_slug}.diagnostic"],
                    criteria=CriteriaEntry(min_attempts=2, min_accuracy=0.0),
                    focus="Onboarding/Diagnostic calibration phase"
                )
            ]
            # This diagnostic plan is what the learner starts under — make it
            # the confirmed baseline for change authority.
            from datetime import datetime as _dt, timezone as _tz
            from .tasks import authority as _authority

            campaign.pedagogical_journal.append({
                "timestamp": _dt.now(_tz.utc).isoformat(),
                "action": _authority.PLAN_CONFIRMED,
                "trigger": "campaign create (onboarding diagnostic plan)",
                "hypothesis": "initial diagnostic plan confirmed at creation",
                "status": "applied",
                "plan_snapshot": [p.model_dump() for p in campaign.attack_plan],
            })
            api.store.campaigns.save(campaign)

        # 5. Start practice session (onboarding questions JIT trigger)
        session_id = None
        exercise_ids = []

        if not _use_json(args):
            sess_res = api.start_practice_session(campaign_id=campaign_id)
            session = sess_res["session"]
            if session is None:
                console.print("\n[yellow]Diagnostic questions need an AI fulfiller.[/yellow]")
                for t in sess_res.get("tasks", []):
                    console.print(f"  Pending task [cyan]{t['id']}[/cyan] — {t['submit_with']}")
                console.print(
                    "  Fulfill the task(s) (or configure a model: dojo config set model.command \"<cmd>\" "
                    "then dojo task run), then run [bold]dojo campaign resume[/bold] via [bold]dojo start[/bold].\n"
                )
                return 0
            session_id = session["id"]
            exercise_ids = session["exercise_ids"]

            # Fetch campaign details after JIT update
            updated_campaign = api.store.campaigns.get(campaign_id)
            campaign_name = updated_campaign.name if updated_campaign else args.goal
            campaign_topic = updated_campaign.topic_path if updated_campaign else temp_slug

            # 6. Render detected topic and title
            header_text = (
                f"[bold green]Campaign Name:[/bold green] [yellow]{campaign_name}[/yellow]\n"
                f"[bold green]Campaign ID:[/bold green] [cyan]{campaign_id}[/cyan]\n"
                f"[bold green]Topic Path Namespace:[/bold green] [cyan]{campaign_topic}[/cyan]"
            )
            console.print(Panel(header_text, title="🚀 [bold green]Campaign Onboarding Diagnostic[/bold green]", expand=False, border_style="green"))

            # 7. Styled interactive questions loop
            console.print("\n[bold yellow]To calibrate your study plan, please answer the following diagnostic questions:[/bold yellow]")
            for idx in range(len(exercise_ids)):
                prompt_info = api.reveal_prompt(session_id=session_id)
                prompt = prompt_info["prompt"]

                console.print()
                console.print(Panel(
                    prompt,
                    title=f"[bold yellow]Question {idx + 1} of {len(exercise_ids)}[/bold yellow]",
                    border_style="yellow",
                    expand=False
                ))

                user_answer = ""
                while not user_answer.strip():
                    user_answer = console.input("[bold cyan]Answer >>> [/bold cyan]").strip()

                api.submit_answer(user_answer=user_answer, session_id=session_id)

            # 8. Trigger reflection/consolidation
            api.consolidate_learner_profile(campaign_id=campaign_id)

            # Fetch finalized details
            camp_data = api.store.campaigns.get(campaign_id)

            if camp_data:
                if camp_data.syllabus_markdown:
                    from rich.markdown import Markdown
                    console.print()
                    console.print(Panel(
                        Markdown(camp_data.syllabus_markdown),
                        title="📚 [bold green]Campaign Syllabus[/bold green]",
                        border_style="green"
                    ))

                if camp_data.attack_plan:
                    from rich.tree import Tree
                    tree = Tree("[bold cyan]Curriculum Attack Plan Timeline[/bold cyan]")
                    for p in camp_data.attack_plan:
                        phase_idx = p.phase
                        topics_str = ", ".join(p.topics or [])
                        crit = p.criteria
                        criteria_str = f"min_attempts={crit.min_attempts}, min_accuracy={crit.min_accuracy}"

                        if phase_idx == camp_data.active_phase_index:
                            phase_node = tree.add(f"[bold yellow]▶ Phase {phase_idx} (Active)[/bold yellow]")
                            phase_node.add(f"[bold yellow]Topics:[/bold yellow] [yellow]{topics_str}[/yellow]")
                            phase_node.add(f"[bold yellow]Target Criteria:[/bold yellow] [dim]{criteria_str}[/dim]")
                        else:
                            status_style = "dim" if phase_idx < camp_data.active_phase_index else "cyan"
                            phase_node = tree.add(f"[{status_style}]Phase {phase_idx}[/{status_style}]")
                            phase_node.add(f"[bold {status_style}]Topics:[/bold {status_style}] {topics_str}")
                            phase_node.add(f"[bold {status_style}]Target Criteria:[/bold {status_style}] [dim]{criteria_str}[/dim]")
                    console.print()
                    console.print(tree)

            console.print("\n[bold green]Campaign setup and diagnostic calibration complete![/bold green]")
            console.print("To begin practicing, run: [bold cyan]dojo start[/bold cyan]\n")

        else:
            # JSON mode: start the session to trigger diagnostic task emission,
            # then hand the agent everything it needs in one envelope.
            sess_res = api.start_practice_session(campaign_id=campaign_id)
            # OP #16: echo the campaign AS SAVED (diagnostic stamp, ungated
            # phase 1) — the creation-time snapshot predates the overwrite
            # and misreported mode/criteria to agents.
            fresh = api.store.campaigns.get(campaign_id)
            _print_json({
                "ok": True,
                "type": "campaign_created",
                "data": {**res, **(fresh.model_dump() if fresh else {})},
                "session": sess_res.get("session"),
                "tasks": sess_res.get("tasks", []),
                "next": sess_res.get("next") or "run dojo ready to reveal the first prompt",
            })

    except (KeyboardInterrupt, Exception) as exc:
        if not _use_json(args):
            console.print()
            if isinstance(exc, KeyboardInterrupt):
                console.print("[bold red]Campaign creation cancelled. Cleaning up filesystem...[/bold red]")
            else:
                console.print(f"[bold red]Campaign creation failed ({exc}). Cleaning up...[/bold red]")

        # Cleanup created files
        try:
            campaign_dir = api.store.dojo_dir / "campaigns" / f"camp_{temp_slug}"
            if campaign_dir.exists():
                shutil.rmtree(campaign_dir)
            if session_id:
                api.store.sessions.delete_active()
        except Exception as cleanup_exc:
            api.log.error(f"Failed to clean up files during campaign creation cancel: {cleanup_exc}")

        if isinstance(exc, KeyboardInterrupt):
            raise SystemExit(1)
        else:
            raise SystemExit(f"error: campaign creation failed: {exc}")

    return 0


def cmd_campaign_link(args: argparse.Namespace) -> int:
    """`dojo campaign link`: attach a source to a campaign, then re-run consolidation so it grounds future work."""
    api = DojoAPI(_db_path(args))
    try:
        api.attach_source_to_campaign(
            campaign_id=args.campaign_id,
            source_id=args.source_id,
            purpose=args.purpose or "Primary study material"
        )

        if not _use_json(args):
            console.print(f"[bold green]Successfully linked source [cyan]{args.source_id}[/cyan] to campaign [cyan]{args.campaign_id}[/cyan].[/bold green]")

        try:
            res = api.consolidate_learner_profile(campaign_id=args.campaign_id)
        except Exception as exc:
            raise SystemExit(f"error: profile consolidation failed: {exc}")

        if _use_json(args):
            _print_json({
                "ok": True,
                "type": "campaign_linked",
                "data": res
            })
        else:
            console.print("[bold green]Source topics mapped successfully.[/bold green]")
            camp = api.store.campaigns.get(args.campaign_id)

            if camp and camp.sources_config:
                table = Table(title="Linked Campaign Sources")
                table.add_column("Source ID", style="cyan")
                table.add_column("Purpose", style="green")
                table.add_column("Mapped Topics", style="magenta")
                for link in camp.sources_config:
                    table.add_row(
                        link["source_id"],
                        link.get("purpose", ""),
                        ", ".join(link.get("topics") or [])
                    )
                console.print(table)
    except Exception as exc:
        raise SystemExit(f"error: linking source failed: {exc}")
    return 0


def cmd_campaign_history(args: argparse.Namespace) -> int:
    """`dojo campaign history`: the pedagogical journal (creation, phase advances, reflections), newest first."""
    api = DojoAPI(_db_path(args))
    try:
        res = api.get_campaign_history(args.campaign)
    except Exception as exc:
        raise SystemExit(f"error: failed to retrieve campaign history: {exc}")

    if _use_json(args):
        _print_json({
            "ok": True,
            "type": "campaign_history",
            "data": res
        })
    else:
        campaign_name = "Global History"
        campaign_id_disp = args.campaign or "All"
        
        console.print(f"\n[bold green]Pedagogical Journal for Campaign: {campaign_name}[/bold green]")
        console.print(f"  Campaign ID: [cyan]{campaign_id_disp}[/cyan]\n")

        if not res["history"]:
            console.print("No journal entries logged yet.")
            return 0

        for i, entry in enumerate(res["history"], 1):
            timestamp_short = entry["timestamp"].split("T")[0] if entry.get("timestamp") else "N/A"
            console.print(
                f"[bold cyan][{i}] {timestamp_short} - Action: {entry.get('action')}[/bold cyan] "
                f"(Campaign: {entry.get('campaign_id')}, Status: {entry.get('status', 'resolved')})"
            )
            console.print(f"    [bold]Trigger:[/bold] {entry.get('trigger')}")
            console.print(f"    [bold]Hypothesis:[/bold] {entry.get('hypothesis')}")
            console.print()
    return 0


def cmd_campaign_export(args: argparse.Namespace) -> int:
    """`dojo campaign export`: write a campaign's syllabus to PDF or markdown ('latest' picks the most recently active)."""
    api = DojoAPI(_db_path(args))
    campaign_id = args.campaign

    if campaign_id == "latest":
        try:
            history = api.get_campaign_history(None)
            if history["history"]:
                campaign_id = history["history"][0]["campaign_id"]
            else:
                raise ValueError("no campaigns exist to export")
        except Exception as exc:
            raise SystemExit(f"error: failed to resolve latest campaign: {exc}")

    output_path = args.output
    if not output_path:
        try:
            camp = api.store.campaigns.get(campaign_id)
            if not camp:
                raise ValueError(f"Campaign '{campaign_id}' not found")
            name_slug = "".join(c for c in camp.name.lower() if c.isalnum() or c == " ").strip().replace(" ", "_")[:30]
            if not name_slug:
                name_slug = campaign_id
            ext = "pdf" if args.format == "pdf" else "md"
            output_path = f"{name_slug}_syllabus.{ext}"
        except Exception as exc:
            raise SystemExit(f"error: failed to get campaign details: {exc}")

    try:
        res = api.export_campaign_syllabus(
            campaign_id=campaign_id,
            output_path=output_path,
            format=args.format
        )
    except Exception as exc:
        raise SystemExit(f"error: failed to export campaign: {exc}")

    if _use_json(args):
        _print_json({
            "ok": True,
            "type": "campaign_export",
            "data": res
        })
    else:
        console.print(f"[bold green]Syllabus successfully exported![/bold green]")
        console.print(f"  Campaign: [cyan]{campaign_id}[/cyan]")
        console.print(f"  Format: [cyan]{res['format'].upper()}[/cyan]")
        console.print(f"  Output Path: [cyan]{res['path']}[/cyan]")
    return 0


def cmd_task_list(args: argparse.Namespace) -> int:
    """`dojo task list`: tasks as JSON (optionally by --status), with fulfillment instructions in `next`."""
    from .store import DojoStore

    store = DojoStore(_db_path(args))
    filters = {"status": args.status} if args.status else None
    tasks = store.tasks.list(filters=filters)
    _print_json({
        "tasks": [
            {
                "id": t.id, "kind": t.kind, "status": t.status,
                "campaign_id": t.campaign_id, "created_at": t.created_at,
                "payload_bytes": t.payload_bytes, "submissions": t.submissions,
            }
            for t in tasks
        ],
        "next": "fulfill each pending task: read its prompt (dojo task show <id> --prompt), "
                "produce the JSON it asks for, then: dojo task submit <id>",
    })
    return 0


def cmd_task_show(args: argparse.Namespace) -> int:
    """`dojo task show`: one task as JSON; --prompt prints only the raw prompt
    body (pipe it to a model); --trace prints the submission history — the
    model's own words, verbatim, behind whatever this task produced."""
    from .store import DojoStore

    store = DojoStore(_db_path(args))
    task = store.tasks.get(args.task_id)
    if task is None:
        _print_json({"ok": False, "error": f"no such task: {args.task_id}"})
        return 1
    if args.prompt:
        print(task.prompt)
        return 0
    if getattr(args, "trace", False):
        if _use_json(args):
            _print_json({"ok": True, "task_id": task.id, "kind": task.kind,
                         "status": task.status, "trace": task.trace})
            return 0
        if not task.trace:
            console.print("[dim]no submissions yet — the task is still pending[/dim]")
            return 0
        for i, entry in enumerate(task.trace, 1):
            mark = "[green]✓ accepted[/green]" if entry.get("ok") else "[red]✗ rejected[/red]"
            console.print(f"\n[bold]submission {i}[/bold] · {entry.get('at', '?')} · {mark}")
            for err in entry.get("errors", []):
                console.print(f"  [red]{err}[/red]")
            console.print(entry.get("raw", ""))
        return 0
    _print_json({**task.model_dump(exclude={"prompt"}), "prompt": task.prompt})
    return 0


def cmd_task_submit(args: argparse.Namespace) -> int:
    """`dojo task submit`: feed result JSON (stdin or --file) through the one validated door; exit 1 on rejection."""
    from .store import DojoStore
    from .tasks import service

    store = DojoStore(_db_path(args))
    if args.file:
        raw = Path(args.file).read_text(encoding="utf-8")
    else:
        raw = sys.stdin.read()
    outcome = service.submit(store, args.task_id, raw)
    _print_json({
        "ok": outcome.ok, "task_id": outcome.task_id, "status": outcome.status,
        "errors": outcome.errors, "applied": outcome.applied,
        "next": None if outcome.ok else (
            "fix the listed errors and resubmit the corrected JSON"
            if outcome.status == "pending" else "task is closed; re-run the originating command to re-emit"
        ),
    })
    return 0 if outcome.ok else 1


def cmd_task_run(args: argparse.Namespace) -> int:
    """Drains pending tasks through a one-string fulfiller command (QUESTIONS.md
    Q1): prompt on stdin → stdout salvage-extracted → the same validated submit
    path every other fulfiller uses."""
    import shlex
    import subprocess as sp

    from .store import DojoStore
    from .tasks import service

    store = DojoStore(_db_path(args))
    command = (args.command or store.configs.get_value("model.command")
               or store.configs.get_value("fulfiller.command"))
    if not command:
        _print_json({
            "ok": False,
            "error": "no model command: pass --command or set `dojo config set model.command \"<cmd>\"`",
        })
        return 1

    pending = store.tasks.list(filters={"status": "pending"})
    if args.limit:
        pending = pending[: args.limit]
    results, ok_count = [], 0
    for task in pending:
        try:
            proc = sp.run(
                shlex.split(command), input=task.prompt,
                capture_output=True, text=True, timeout=args.timeout,
            )
            if proc.returncode != 0:
                results.append({"task_id": task.id, "ok": False,
                                "error": f"fulfiller exited {proc.returncode}: {proc.stderr.strip()[:200]}"})
                continue
            outcome = service.submit(store, task.id, proc.stdout)
            ok_count += outcome.ok
            results.append({"task_id": task.id, "ok": outcome.ok,
                            "status": outcome.status, "errors": outcome.errors})
        except sp.TimeoutExpired:
            results.append({"task_id": task.id, "ok": False,
                            "error": f"fulfiller timed out after {args.timeout}s"})
    _print_json({
        "ok": ok_count == len(pending),
        "fulfilled": ok_count, "attempted": len(pending), "results": results,
    })
    return 0 if ok_count == len(pending) else 1


def _score_bar(score: float, width: int = 10) -> str:
    filled = round(score * width)
    return "█" * filled + "░" * (width - filled)


def _score_style(score: float) -> str:
    return "green" if score >= 0.8 else ("yellow" if score >= 0.5 else "red")


def _detect_install_method(
    *, executable: Path, prefix: Path, frozen: bool, home: Path, argv0: Path
) -> tuple[str, str]:
    """How was this dojo installed? sys.prefix is the reliable venv signal —
    sys.executable must stay UNRESOLVED, because resolving a venv's python
    symlink jumps to the base interpreter (e.g. Homebrew's framework python)
    and misreports a venv install as bare pip (owner-reported bug)."""
    if frozen:
        return ("binary", f"rm {argv0}")
    if "pipx" in str(prefix) or "pipx" in str(executable):
        return ("pipx", "pipx uninstall dojo")
    if str(prefix).startswith(str(home / ".dojo")):
        return ("venv", f"rm -rf {home / '.dojo'} {home / '.local/bin/dojo'}")
    return ("pip", f"{executable} -m pip uninstall dojo")


def _self_uninstall_plan(method: str, *, home: Path, argv0: Path,
                         executable: Path) -> list[dict[str, str]]:
    """What removing THIS install means, as inspectable actions the executor
    performs (and the human flow renders before confirming). Uninstall
    reverses install and nothing else: learning data is never in the plan,
    and a launcher that doesn't point into ~/.dojo is not ours to delete."""
    if method == "venv":
        plan = [{"do": "rmtree", "target": str(home / ".dojo")}]
        launcher = home / ".local" / "bin" / "dojo"
        if launcher.is_symlink() or launcher.exists():
            try:
                if launcher.is_symlink():
                    owned = str(launcher.readlink()).startswith(str(home / ".dojo"))
                else:  # a copied console script: its shebang names our venv python
                    first = launcher.read_text(encoding="utf-8", errors="ignore").split("\n", 1)[0]
                    owned = str(home / ".dojo" / "venv") in first
            except OSError:
                owned = False
            plan.append(
                {"do": "unlink", "target": str(launcher)} if owned else
                {"do": "skip", "target": str(launcher),
                 "reason": "exists but does not point at ~/.dojo — not ours, left alone"}
            )
        return plan
    if method == "binary":
        return [{"do": "unlink", "target": str(argv0)}]
    if method == "pipx":
        return [{"do": "run", "target": "pipx uninstall dojo"}]
    return [{"do": "run", "target": f"{executable} -m pip uninstall -y dojo"}]


def _execute_uninstall_plan(plan: list[dict[str, str]]) -> tuple[list[str], list[str]]:
    """Performs the plan; returns (removed, errors). Deleting our own venv
    while running is safe on POSIX — open files keep their inodes until the
    process exits — so act first, report after."""
    import shlex as _shlex
    import shutil as _shutil
    import subprocess as _subprocess

    removed: list[str] = []
    errors: list[str] = []
    for act in plan:
        try:
            if act["do"] == "rmtree":
                _shutil.rmtree(act["target"])
            elif act["do"] == "unlink":
                Path(act["target"]).unlink()
            elif act["do"] == "run":
                proc = _subprocess.run(_shlex.split(act["target"]),
                                       capture_output=True, text=True)
                if proc.returncode != 0:
                    errors.append(f"{act['target']}: {proc.stderr.strip()[:160]}")
                    continue
            else:  # "skip" — rendered, never executed
                continue
            removed.append(act["target"])
        except OSError as exc:
            errors.append(f"{act['target']}: {exc}")
    return removed, errors


def cmd_export(args: argparse.Namespace) -> int:
    """`dojo export`: write the whole store as a fresh markdown store at an empty destination."""
    from .export import export_store
    from .store import DojoStore

    store = DojoStore(_db_path(args))
    try:
        summary = export_store(store, args.destination)
    except ValueError as exc:
        _print_json({"ok": False, "error": str(exc)})
        return 1
    _print_json({"ok": True, **summary})
    return 0


def cmd_uninstall(args: argparse.Namespace) -> int:
    """Removes what install created: the skill from an agent's directory, and
    (--self) the dojo program itself. Learning data (~/.local/share/dojo) is
    NEVER touched — it is the user's learning life; removing it is a manual,
    deliberate act."""
    import shutil as _shutil

    removed = []

    if getattr(args, "self_uninstall", False):
        method, manual_cmd = _detect_install_method(
            executable=Path(sys.executable),
            prefix=Path(sys.prefix),
            frozen=bool(getattr(sys, "frozen", False)),
            home=Path.home(),
            argv0=Path(sys.argv[0]),
        )
        plan = _self_uninstall_plan(method, home=Path.home(),
                                    argv0=Path(sys.argv[0]),
                                    executable=Path(sys.executable))
        note = ("your learning data is untouched; delete it manually only if you "
                "are sure — it is your entire practice history")
        human = not _use_json(args)
        if human:
            console.print(f"[bold]Uninstalling dojo[/bold] [dim]({method} install)[/dim] — removing:")
            for act in plan:
                if act["do"] == "skip":
                    console.print(f"  [dim]leaving {act['target']} — {act['reason']}[/dim]")
                else:
                    console.print(f"  [cyan]{act['target']}[/cyan]")
            console.print(f"Your learning data stays: [green]{DEFAULT_DOJO_DIR}[/green]")
            if not getattr(args, "yes", False):
                from .interactive import confirm
                if not confirm("Remove dojo?", default=False):
                    console.print("[dim]Nothing removed.[/dim]")
                    return 0
        removed, errors = _execute_uninstall_plan(plan)
        if human:
            for r in removed:
                console.print(f"  [green]✓ removed[/green] {r}")
            for e in errors:
                console.print(f"  [red]✗ {e}[/red]")
            if errors:
                console.print(f"[yellow]Finished with errors — manual fallback:[/yellow] {manual_cmd}")
                return 1
            console.print(f"\n[bold green]dojo is gone.[/bold green] {note.capitalize()}")
            return 0
        _print_json({
            "ok": not errors,
            "install_method": method,
            "removed": removed,
            **({"errors": errors, "manual_fallback": manual_cmd} if errors else {}),
            "learning_data": str(DEFAULT_DOJO_DIR),
            "note": note,
        })
        return 1 if errors else 0

    agent = getattr(args, "agent", None)
    dest = getattr(args, "dest", None)
    home = Path.home()
    if dest:
        target_path = Path(dest)
    elif agent == "hermes":
        target_path = home / ".hermes" / "skills" / "dojo"
    elif agent == "openclaw":
        target_path = home / ".openclaw" / "skills" / "dojo"
    elif agent:
        target_path = home / f".{agent}" / "skills" / "dojo"
    else:
        raise SystemExit("specify an agent name, --dest <path>, or --self")

    human = not _use_json(args)
    if not target_path.exists():
        if human:
            console.print(f"[yellow]Nothing installed at {target_path}.[/yellow]")
        else:
            _print_json({"ok": True, "removed": [], "note": f"nothing installed at {target_path}"})
        return 0
    if not _is_owned_by_dojo(target_path):
        msg = (f"{target_path} exists but is not a dojo-owned skill "
               "(no dojo owner marker in SKILL.md) — refusing to delete it")
        if human:
            console.print(f"[red]✗ {msg}[/red]")
        else:
            _print_json({"ok": False, "error": msg})
        return 1
    _shutil.rmtree(target_path)
    removed.append(str(target_path))
    if human:
        console.print(f"[green]✓ removed[/green] {target_path}\n"
                      f"Learning data untouched ([green]{DEFAULT_DOJO_DIR}[/green]) — "
                      "[dim]dojo uninstall --self removes the program itself.[/dim]")
        return 0
    _print_json({
        "ok": True,
        "removed": removed,
        "learning_data": str(DEFAULT_DOJO_DIR),
        "note": "skill removed; learning data untouched (dojo uninstall --self for the program itself)",
    })
    return 0


def cmd_benchmark(args: argparse.Namespace) -> int:
    """Benchmarks the user's model(s) on dojo's shipped pedagogy corpus and
    shows, by category, where that (driver, judge) pair is strong or weak —
    headline first, full detail opt-in (--detail)."""
    import tempfile
    from datetime import datetime, timezone

    from .evals.runner import run_benchmark, run_holdout_gate

    driver = args.driver
    # Judge resolution: explicit -j wins; else the configured standing judge
    # (benchmark.judge — owner 2026-07-11: "codex should grade"); only then
    # the driver itself — self-judging is a choice, never an accident.
    store = DojoStore(_db_path(args))
    judge = (
        args.judge
        or str(store.configs.get_value("benchmark.judge", "") or "").strip()
        or driver
    )

    if getattr(args, "skill", False):
        # The OTHER axis, in isolation (owner directive 2026-07-18): "how
        # well does this agent execute dojo WORKFLOWS through SKILL.md?" —
        # distinct from "how well does it fulfill dojo tasks". A user who
        # only plans to coordinate with a model benchmarks just this;
        # deterministic outcome checks only, so no judge spend.
        from .evals.skill_runner import load_skill_corpus, run_skill_scenario

        scenarios = load_skill_corpus()
        results = []
        with tempfile.TemporaryDirectory(prefix="dojo-skill-") as workdir:
            for sc in scenarios:
                if not _use_json(args):
                    console.print(f"  [dim]· workflow · {sc['name']}[/dim]")
                try:
                    results.append(run_skill_scenario(
                        sc, Path(workdir) / sc["name"], driver,
                        timeout=args.timeout,
                    ))
                except Exception as exc:
                    results.append({"name": sc["name"], "score": 0.0,
                                    "checks": {}, "error": str(exc)[:200]})
        scored = [r for r in results if "error" not in r]
        overall = (sum(r["score"] for r in scored) / len(scored)) if scored else None
        if _use_json(args):
            _print_json({"ok": True, "tier": "skill", "driver": driver,
                         "overall": overall, "scenarios": results})
            return 0
        console.print("\n[bold]🥋 Skill workflows[/bold] "
                      "[dim](driver-side: SKILL.md coordination, outcome checks)[/dim]")
        for r in results:
            bar = "[red]✗[/red]" if r.get("error") or r["score"] < 1.0 else "[green]✓[/green]"
            console.print(f"  {bar} {r['name']:<28} {r['score']:.2f}"
                          + (f"  [red]{r['error']}[/red]" if r.get("error") else ""))
            for cname, c in r.get("checks", {}).items():
                if not c["ok"]:
                    console.print(f"      [dim]{cname}: {c['detail'][:90]}[/dim]")
        if overall is not None:
            console.print(f"\n  [bold]workflow score {overall:.2f}[/bold] over "
                          f"{len(scored)} scenario(s)"
                          + (f" · {len(results) - len(scored)} errored" if len(results) != len(scored) else ""))
        console.print("  [dim]fulfiller-side pedagogy: dojo benchmark -d <model cmd> (separate axis)[/dim]")
        return 0

    if getattr(args, "holdout", False):
        # Release gate: structurally aggregate-only (owner ruling — holdout
        # data must never optimize prompts; the tool can't show what the
        # runner never returns).
        def hprogress(msg: str) -> None:
            if not _use_json(args):
                console.print(f"  [dim]·[/dim] {msg}")

        with tempfile.TemporaryDirectory(prefix="dojo-holdout-") as workdir:
            gate = run_holdout_gate(
                driver=driver, judge=judge, workdir=Path(workdir),
                timeout=args.timeout, progress=hprogress,
            )
        # Compute THE one consumable bit when the visible pair baseline is
        # reachable (repo checkout): gap = visible mean − holdout mean.
        visible_file = Path("evals/baselines") / f"{gate['pair']}.json"
        if visible_file.exists() and gate["mean_quality"] is not None:
            visible = json.loads(visible_file.read_text(encoding="utf-8"))
            if visible.get("mean_quality") is not None:
                gate["visible_mean"] = round(visible["mean_quality"], 3)
                gate["generalization_gap"] = round(
                    visible["mean_quality"] - gate["mean_quality"], 3)
        if _use_json(args):
            _print_json({"ok": True, **gate})
            return 0
        console.print("\n[bold]🥋 Holdout gate[/bold] [dim](aggregate only, by design)[/dim]")
        mean = gate["mean_quality"]
        console.print(
            f"  scored {gate['scored']}/{gate['scenarios']} · "
            f"compliance failures {gate['compliance_failures']} · "
            f"judge/infra errors {gate['infrastructure_or_judge_errors']}"
        )
        if mean is None:
            console.print("  [red]no scoreable result[/red]")
        elif gate.get("visible_mean") is not None:
            gap = gate["generalization_gap"]
            verdict = ("[green]prompts generalize[/green]" if gap <= 0.1 else
                       "[yellow]watch: moderate gap[/yellow]" if gap <= 0.2 else
                       "[red]OVERFIT: broaden the visible corpus[/red]")
            console.print(f"  [bold]holdout mean {mean:.3f}[/bold] · visible mean "
                          f"{gate['visible_mean']:.3f} · gap {gap:+.3f} → {verdict}")
            console.print("  [dim]Remedy for a bad gap: broaden the VISIBLE corpus and iterate "
                          "there. Never read holdout contents.[/dim]")
        else:
            console.print(f"  [bold]holdout mean {mean:.3f}[/bold] — no visible pair baseline "
                          "found in ./evals/baselines to compare against.")
        return 0

    tiers = ("compliance",) if args.tier == "compliance" else (
        ("quality",) if args.tier == "quality" else ("compliance", "quality")
    )

    if not _use_json(args):
        console.print("\n[bold]🥋 Dojo model benchmark[/bold]")
        console.print(f"  Driver (does the work):   [cyan]{driver}[/cyan]")
        if "quality" in tiers:
            console.print(f"  Judge  (grades quality):  [cyan]{judge}[/cyan]")
        else:
            console.print("  [dim]compliance tier: scored by validators — no judge involved[/dim]")
        console.print("  [dim]This drives your models on real scenarios — expect several minutes.[/dim]\n")

    # Live pane (owner ask 2026-07-11: "visualize the speed and its
    # reasoning"): anchored summary on top, a rolling tail of the model's
    # raw stream below — deliberately NOT scrollable; the full output lands
    # in the report JSON for reading, the pane is for watching it think.
    live_mode = not _use_json(args) and sys.stdout.isatty()

    if not live_mode:
        def progress(msg: str) -> None:
            if not _use_json(args):
                console.print(f"  [dim]·[/dim] {msg}")

        with tempfile.TemporaryDirectory(prefix="dojo-bench-") as workdir:
            report = run_benchmark(
                driver=driver, judge=judge, workdir=Path(workdir),
                timeout=args.timeout, tiers=tiers, progress=progress,
            )
    else:
        import time as _time
        from collections import deque

        from rich.console import Group
        from rich.live import Live
        from rich.text import Text

        from .evals.runner import set_stream_observer

        TAIL_LINES = 14
        state = {"stage": "starting…", "done": 0, "call_start": 0.0, "chars": 0,
                 "tail": deque(maxlen=4096)}

        def _render():
            elapsed = max(_time.monotonic() - state["call_start"], 1e-6)
            toks = state["chars"] / 4 / elapsed if state["chars"] else 0.0
            head = Text.assemble(
                ("🥋 ", ""), (driver, "cyan"),
                (f"  ·  {state['stage']}", "bold"),
                (f"  ·  {state['done']} step(s) done", "dim"),
                (f"  ·  ≈{toks:5.1f} tok/s", "yellow" if toks else "dim"),
            )
            tail = "".join(state["tail"]).splitlines()[-TAIL_LINES:]
            body = Text("\n".join(tail) or "(waiting for the model…)", style="dim")
            return Panel(Group(head, Text("─" * 60, style="dim"), body),
                         title="[bold]live[/bold]", border_style="cyan")

        with Live(_render(), console=console, refresh_per_second=8,
                  vertical_overflow="crop") as live:
            def progress(msg: str) -> None:
                state["stage"] = msg
                state["done"] += 1
                live.update(_render())

            def observer(event: dict) -> None:
                if event["kind"] == "call_start":
                    state["call_start"] = _time.monotonic()
                    state["chars"] = 0
                    state["tail"].clear()
                else:
                    state["chars"] += len(event["text"])
                    state["tail"].extend(event["text"])
                live.update(_render())

            set_stream_observer(observer)
            try:
                with tempfile.TemporaryDirectory(prefix="dojo-bench-") as workdir:
                    report = run_benchmark(
                        driver=driver, judge=judge, workdir=Path(workdir),
                        timeout=args.timeout, tiers=tiers, progress=progress,
                    )
            finally:
                set_stream_observer(None)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_path = Path(args.output or f"dojo-benchmark-{report['pair']}-{stamp}.json")
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if _use_json(args):
        _print_json(report)
        return 0

    console.print()
    overall = report["overall"]
    if report["errors"]:
        console.print(
            f"  [bold red]⚠ {report['errors']} of {report['total_scenarios']} scenarios "
            f"could not be scored[/bold red] — scores below cover only the "
            f"{report['scored_scenarios']} that ran cleanly (--detail shows the errors)\n"
        )
    if overall is None:
        console.print("  [bold red]No scenario produced a scoreable result.[/bold red]\n")
    else:
        console.print(
            f"  [bold]Overall[/bold]  [{_score_style(overall)}]{_score_bar(overall)} "
            f"{overall:.2f}[/{_score_style(overall)}]  "
            f"[dim]({report['scored_scenarios']} of {report['total_scenarios']} scenarios scored)[/dim]\n"
        )

    if report.get("token_footprint"):
        tf = report["token_footprint"]
        console.print(
            f"  [bold]Context economy[/bold]  ~{tf['approx_prompt_tokens']} tokens per task in, "
            f"~{tf['approx_response_tokens']} out  "
            f"[dim](measured over {tf['driver_calls_measured']} driver calls)[/dim]\n"
        )

    table = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
    table.add_column("Category")
    table.add_column("Score", justify="left")
    table.add_column("What it measures", style="dim")
    for name, cat in report["categories"].items():
        if cat["mean"] is None:
            table.add_row(name, f"[red]no result ({cat['errors']} error(s))[/red]", cat["blurb"])
        else:
            style = _score_style(cat["mean"])
            table.add_row(name, f"[{style}]{_score_bar(cat['mean'])} {cat['mean']:.2f}[/{style}]", cat["blurb"])
    console.print(table)

    cats = [(n, c) for n, c in report["categories"].items() if c["mean"] is not None]
    if len(cats) >= 2:
        best, worst = cats[0], cats[-1]
        console.print(
            f"\n  [green]Strongest:[/green] {best[0]} ({best[1]['mean']:.2f})"
            f"\n  [red]Weakest:[/red]   {worst[0]} ({worst[1]['mean']:.2f}) — {worst[1]['blurb']}"
        )

    if args.detail:
        console.print("\n[bold]Per-scenario detail[/bold]")
        for name, cat in report["categories"].items():
            console.print(f"\n  [bold]{name}[/bold]")
            for sc in cat["scenarios"]:
                style = _score_style(sc["score"])
                line = f"    [{style}]{sc['score']:.2f}[/{style}]  {sc['name']}"
                if sc.get("error"):
                    line += f"  [red]⚠ {sc['error']}[/red]"
                console.print(line)
                for cid, verdict in (sc.get("detail", {}).get("verdicts") or {}).items():
                    mark = "[green]✓[/green]" if verdict == "pass" else f"[red]✗[/red] [dim]{verdict}[/dim]"
                    console.print(f"        {cid} {mark}")
                for err in (sc.get("detail", {}).get("errors") or [])[:2]:
                    console.print(f"        [red]{err}[/red]")
    else:
        console.print("\n  [dim]Run with --detail for per-scenario criterion verdicts.[/dim]")

    console.print(f"\n  Report saved: [cyan]{out_path}[/cyan]\n")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    """`dojo stats`: per-campaign retention/due/accuracy/idle plus AI token spend, estimates tagged."""
    api = DojoAPI(_db_path(args))
    res = api.stats()
    if _use_json(args):
        _print_json({"ok": True, **res})
        return 0
    table = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
    for col in ("Campaign", "Retention*", "Due", "Accuracy (20)", "Idle", "Insights"):
        table.add_column(col)
    for c_ in res["campaigns"]:
        ret = "—" if c_["estimated_retention"] is None else f"{c_['estimated_retention']:.0%}"
        acc = "—" if c_["recent_accuracy"] is None else f"{c_['recent_accuracy']:.0%}"
        idle = "—" if c_["days_since_practice"] is None else f"{c_['days_since_practice']:.0f}d"
        table.add_row(c_["name"], ret, f"{c_['due_now']}/{c_['active_exercises']}", acc, idle,
                      str(c_["active_insights"]))
    console.print(table)
    console.print("  [dim]*estimated mean recall odds over tracked fact memories[/dim]")
    if res["task_spend"]:
        console.print("\n[bold]AI task spend[/bold] [dim](~4 bytes ≈ 1 token)[/dim]")
        for kind, k in res["task_spend"].items():
            console.print(
                f"  {kind}: {k['tasks']} task(s), ~{k['approx_prompt_tokens']} tokens in / "
                f"~{k['approx_response_tokens']} out"
                + (f", [red]{k['failed']} failed[/red]" if k.get("failed") else "")
            )
    if res["inbox_waiting"]:
        console.print(f"\n  [yellow]{res['inbox_waiting']} capture(s) awaiting a home — dojo inbox[/yellow]")
    return 0


def cmd_capture(args: argparse.Namespace) -> int:
    """`dojo capture`: durably save one utterance BEFORE any AI runs; TTY gets the capture->route->confirm flow, agents get the envelope."""
    api = DojoAPI(_db_path(args))
    if not _use_json(args):
        from .interactive import capture_flow
        return capture_flow(api, text=args.text, why=args.why, locator=args.locator)
    res = api.capture(args.text, why=args.why, locator=args.locator)
    _print_json({"ok": True, **res})
    return 0


def cmd_inbox(args: argparse.Namespace) -> int:
    """`dojo inbox [confirm|dismiss]`: triage captures awaiting a home; bare TTY invocation walks them interactively."""
    api = DojoAPI(_db_path(args))
    if not _use_json(args) and not args.inbox_command:
        from .interactive import inbox_flow
        return inbox_flow(api)
    # OP #18: a misordered call (confirm before the route is fulfilled) is an
    # honest refusal on the agent door, never a traceback.
    try:
        if args.inbox_command == "confirm":
            _print_json({"ok": True, **api.inbox_confirm(args.capture_id)})
        elif args.inbox_command == "dismiss":
            _print_json({"ok": True, **api.inbox_dismiss(args.capture_id)})
        else:
            _print_json({"ok": True, **api.inbox()})
    except ValueError as exc:
        _print_json({"ok": False, "error": str(exc),
                     "next": "dojo inbox lists captures and their route status"})
        return 1
    return 0


def cmd_daily(args: argparse.Namespace) -> int:
    """`dojo daily`: the ritual heartbeat — build or resume today's packet; TTY hands off to the full interactive flow."""
    api = DojoAPI(_db_path(args))
    if not _use_json(args):
        from .interactive import daily_flow
        return daily_flow(api, size=args.size, reset=args.reset, mode=_display_mode(args))
    res = api.daily(size=args.size, reset=args.reset)
    if _use_json(args):
        _print_json({"ok": True, **res})
        return 0
    session = res.get("session")
    if session is None:
        console.print("[yellow]Nothing is due right now.[/yellow]")
        for t in res.get("tasks", []):
            console.print(f"  Pending task [cyan]{t['id']}[/cyan] — {t['submit_with']}")
        console.print(f"  {res.get('next')}")
        return 0
    if not res.get("is_new"):
        console.print(f"[bold yellow]Resuming today's session[/bold yellow] [cyan]{session['id']}[/cyan] "
                      f"({session['current_index']}/{len(session['exercise_ids'])} done)")
        return 0
    console.print(f"[bold green]Today's packet[/bold green] — {len(session['exercise_ids'])} items")
    for item in res.get("items", []):
        console.print(f"  [cyan]{item['exercise_id']}[/cyan]  [dim]{item['reason']}[/dim]")
    for key, count in (res.get("skipped") or {}).items():
        console.print(f"  [dim]{count} due item(s) held back ({key.replace('_', ' ')})[/dim]")
    for t in res.get("tasks", []):
        console.print(f"  Pending task [cyan]{t['id']}[/cyan] — {t['submit_with']}")
    console.print("  Run [bold]dojo ready[/bold] to reveal the first prompt.")
    return 0


def cmd_more(args: argparse.Namespace) -> int:
    """`dojo more`: the capacity channel — answers an explicit ask for extra
    practice with a bounded acquisition top-up, or refuses honestly with the
    7-day review-debt projection. Never offered; only discovered via the
    daily-completion message."""
    api = DojoAPI(_db_path(args))
    if not _use_json(args):
        from .interactive import more_flow
        return more_flow(api, force=bool(getattr(args, "force", False)),
                         mode=_display_mode(args))
    res = api.more(force=bool(getattr(args, "force", False)))
    _print_json({"ok": True, **res})  # a refusal is an answer, not an error
    return 0


def cmd_why(args: argparse.Namespace) -> int:
    """`dojo why`: replay the honest scheduling reason behind every item in the current packet (I9)."""
    api = DojoAPI(_db_path(args))
    res = api.why()
    if _use_json(args):
        _print_json(res)
        return 0
    if res.get("session") is None:
        console.print(f"[yellow]{res['note']}[/yellow]")
        return 0
    console.print(f"[bold]Why this packet[/bold] (session [cyan]{res['session']}[/cyan])")
    for item in res["items"]:
        console.print(f"  [cyan]{item['exercise_id']}[/cyan]  {item['reason']}")
    if res.get("campaigns"):
        console.print("[bold]Campaign ranking[/bold]")
        for cid, reason in res["campaigns"].items():
            console.print(f"  [cyan]{cid}[/cyan]  {reason}")
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    """`dojo plan show|confirm|reject|revert`: the learner's authority over
    AI-proposed plan restructures (show pending, accept, decline, or undo the
    last auto-applied change)."""
    api = DojoAPI(_db_path(args))
    campaign = getattr(args, "campaign", None)
    action = args.plan_command or "show"
    try:
        if action == "confirm":
            res = api.plan_confirm(campaign)
        elif action == "reject":
            res = api.plan_reject(campaign)
        elif action == "revert":
            res = api.plan_revert(campaign)
        else:
            res = api.plan_status(campaign)
    except ValueError as exc:
        raise SystemExit(f"error: {exc}")

    if _use_json(args):
        _print_json({"ok": True, **res})
        return 0
    if action != "show":
        console.print(f"[bold green]✓ plan {res['status']}[/bold green] "
                      f"([cyan]{res['campaign_id']}[/cyan])")
        return 0
    for camp in res["campaigns"]:
        console.print(f"\n[bold]{camp['campaign_id']}[/bold]")
        for p in camp["current_plan"]:
            console.print(f"  Phase {p['phase']}: {', '.join(p['topics'])}"
                          + (f" [dim]— {p['focus']}[/dim]" if p.get("focus") else ""))
        pending = camp["pending_proposal"]
        if pending:
            console.print(f"  [yellow]Proposed restructure[/yellow] — {pending['reason']}")
            for p in pending["proposed_phases"] or []:
                console.print(f"    Phase {p['phase']}: {', '.join(p['topics'])}")
            console.print(f"  Accept: [bold]dojo plan confirm --campaign {camp['campaign_id']}[/bold]"
                          f"  ·  Decline: [bold]dojo plan reject --campaign {camp['campaign_id']}[/bold]")
        elif camp["revertable"]:
            console.print(f"  [dim]last auto-applied change is undoable: "
                          f"dojo plan revert --campaign {camp['campaign_id']}[/dim]")
    return 0


def cmd_learn(args: argparse.Namespace) -> int:
    """`dojo learn "<goal>"`: route-first entry for a learning goal — the goal
    routes against the campaign registry before any new campaign is planned
    (`--new` skips routing). `dojo learn extend|new <task-id>` resolves the
    router's extend-or-start-fresh question."""
    api = DojoAPI(_db_path(args))
    words = args.goal
    verb = (
        words[0]
        if len(words) == 2 and words[0] in ("extend", "new") and words[1].startswith("tsk_")
        else None
    )
    goal = " ".join(words)

    if not _use_json(args):
        from .interactive import learn_flow, plan_flow

        def conversation(context: str | None = None, task_ref: dict | None = None,
                         conv_goal: str = goal) -> int:
            return plan_flow(
                api, goal=conv_goal, level=None, context=context,
                emit_plan_task=lambda g, n: _emit_plan_task(api.store, g, n),
                materialize=lambda tid: _materialize_core(api, tid, None),
                initial_task_ref=task_ref,
                mode=_display_mode(args),
            )

        try:
            if verb == "extend":
                res = api.learn_extend(words[1])
                console.print(f"[bold green]✓[/bold green] {res['next']}")
                return 0
            if verb == "new":
                res = api.learn_new(words[1])
                origin = api.store.tasks.get(words[1])
                return conversation(task_ref=res["tasks"][0],
                                    conv_goal=origin.context.get("goal", goal))
        except ValueError as exc:
            raise SystemExit(f"error: {exc}")
        if args.new or not any(
            c.status == "active" for c in api.store.campaigns.list()
        ):
            return conversation()
        return learn_flow(api, goal=goal, plan_conversation=conversation)

    try:
        if verb == "extend":
            res = api.learn_extend(words[1])
        elif verb == "new":
            res = api.learn_new(words[1])
        else:
            res = api.learn(goal, new=args.new)
    except ValueError as exc:
        raise SystemExit(f"error: {exc}")
    _print_json({"ok": True, **res})
    return 0


def cmd_insights(args: argparse.Namespace) -> int:
    """`dojo insights [show <id> | resolve <id> --because]`: the learner model
    with receipts — see every belief, trace it to your verbatim answers,
    contest it with your own words (ownership block, QUESTIONS 2026-07-09)."""
    api = DojoAPI(_db_path(args))
    action = getattr(args, "insights_command", None)
    try:
        if action == "show":
            res = api.insight_show(args.insight_id)
        elif action == "resolve":
            res = api.insight_resolve(args.insight_id, getattr(args, "because", None) or "")
        else:
            res = api.insights_list(
                campaign_id=getattr(args, "campaign", None),
                include_resolved=bool(getattr(args, "all", False)),
            )
    except ValueError as exc:
        raise SystemExit(f"error: {exc}")

    if _use_json(args):
        _print_json({"ok": True, **res})
        return 0
    if action == "show":
        console.print(f"\n[bold]{res['key']}[/bold] [dim]({res['id']}, {res['status']})[/dim]")
        console.print(f"{res['description']}\n")
        if res.get("resolution"):
            console.print(f"[green]resolved by you:[/green] “{res['resolution']}”\n")
        console.print("[bold]Why we believe this[/bold] — your own answers:")
        for r in res["receipts"]:
            if r.get("note"):
                console.print(f"  [dim]{r['attempt_id']}: {r['note']}[/dim]")
                continue
            console.print(f"  [dim]{r['date']}[/dim] · {r['prompt'][:60]}")
            console.print(f"    [cyan]›[/cyan] “{r['your_answer'][:80]}” — score {r['score']}"
                          f" [dim](graded by {r['grader'] or 'nobody yet'}"
                          + (f", {r['error_tag']}" if r.get("error_tag") else "") + ")[/dim]")
        eff = res["effect"]
        console.print(f"\n[bold]Effect[/bold]: {eff['exercises_targeting']} exercise(s) generated "
                      f"to target this ({eff['last_7_days']} in the last 7 days)")
        console.print(f"[dim]{res['next']}[/dim]")
    elif action == "resolve":
        console.print(f"[green]✓ resolved[/green] — {res['next']}")
    else:
        for camp in res["campaigns"]:
            if not camp["insights"]:
                continue
            console.print(f"\n[bold]{camp['campaign_id']}[/bold]")
            topic = None
            for ins in camp["insights"]:
                if ins["topic"] != topic:
                    topic = ins["topic"]
                    console.print(f"  [bold cyan]{topic}[/bold cyan]")
                mark = "[green]✓[/green] " if ins["status"] == "resolved" else ""
                console.print(f"    {mark}[cyan]{ins['id']}[/cyan] {ins['key']} — {ins['description']}")
                console.print(f"      [dim]{ins['evidence_count']} answer(s) behind it · "
                              f"{ins['age_days']:.0f}d old · updated {ins['last_updated']}[/dim]")
        console.print(f"\n[dim]{res['note']}[/dim]")
        console.print(f"[dim]{res['next']}[/dim]")
    return 0


def cmd_campaign_list(args: argparse.Namespace) -> int:
    """`dojo campaign list`: every campaign — status, plan position, retention
    estimate, dues, idle days (the maintain/archive/extend dashboard)."""
    api = DojoAPI(_db_path(args))
    res = api.campaign_list()
    if _use_json(args):
        _print_json({"ok": True, **res})
        return 0
    from rich.table import Table

    table = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
    for col in ("Campaign", "Status", "Phase", "Retention*", "Due", "Idle"):
        table.add_column(col)
    for c in res["campaigns"]:
        ret = "—" if c["estimated_retention"] is None else f"{c['estimated_retention']:.0%}"
        idle = "—" if c["days_idle"] is None else f"{c['days_idle']:.0f}d"
        status = c["status"] + (" ✓" if c["complete"] else "")
        # The human dashboard leads with the display NAME (owner field report
        # 2026-07-18: the id column exposed slugged-prompt ids); clipped so a
        # legacy long name can't wreck the table. The id rides dimmed — it is
        # what archive/rename/extend commands take.
        label = c["name"] if len(c["name"]) <= 40 else c["name"][:39] + "…"
        table.add_row(f"{label} [dim]{c['campaign_id']}[/dim]",
                      status, c["phase"], ret, str(c["due_now"]), idle)
    console.print(table)
    console.print(f"  [dim]*estimates · {res['next']}[/dim]")
    return 0


def cmd_amend(args: argparse.Namespace) -> int:
    """`dojo amend "<answer>"`: replace a previous answer in the current
    session while its grade is pending (--back N reaches further back). The
    agent door for "wait, change my last answer" — humans use /back inside
    the session; both ride the same API."""
    api = DojoAPI(_db_path(args))
    res = api.amend_previous_answer(args.answer, steps_back=args.back)
    if _use_json(args):
        _print_json(res)
        return 0 if res.get("ok") else 1
    if res.get("ok"):
        console.print(f"[green]✓ amended[/green] [dim](was: {res['superseded'][:60]})[/dim] — {res['next']}")
        return 0
    hint = f" [dim]({res['next']})[/dim]" if res.get("next") else ""
    console.print(f"[yellow]{res['error']}[/yellow]{hint}")
    return 1


def cmd_topic_retire(args: argparse.Namespace) -> int:
    """`dojo topic retire <path>`: the care-exit (ADR 017 §6) — reviews for
    this topic stop now; always reversible with `dojo topic revive`."""
    api = DojoAPI(_db_path(args))
    res = api.topic_retire(args.path, because=args.because or "", campaign_id=args.campaign)
    if _use_json(args):
        _print_json(res)
    else:
        console.print(f"[green]✓[/green] {res.get('note') or res['next']}")
    return 0


def cmd_topic_revive(args: argparse.Namespace) -> int:
    """`dojo topic revive <path>`: reopen a retired topic — its memories
    resume the honest schedule where they left off."""
    api = DojoAPI(_db_path(args))
    res = api.topic_revive(args.path, campaign_id=args.campaign)
    if _use_json(args):
        _print_json(res)
    else:
        console.print(f"[green]✓[/green] {res.get('note') or res['next']}")
    return 0


def _display_mode(args: argparse.Namespace) -> str | None:
    """The app-wide display override: --screen / --transcript beat the
    ui.mode config; absent both, the flows fall back to the config."""
    if getattr(args, "screen", False):
        return "screen"
    if getattr(args, "transcript", False):
        return "transcript"
    return None


def cmd_campaign_rename(args: argparse.Namespace) -> int:
    """`dojo campaign rename <id> "<name>"`: fix a display name in place —
    the id and its history stay (STATE 7f ride-along: paragraph-named
    campaigns fixable without recreating)."""
    api = DojoAPI(_db_path(args))
    try:
        res = api.rename_campaign(args.campaign_id, args.name)
    except ValueError as exc:
        if _use_json(args):
            _print_json({"ok": False, "error": str(exc)})
            return 1
        raise SystemExit(f"error: {exc}")
    if _use_json(args):
        _print_json({"ok": True, **res})
    else:
        console.print(f"[green]✓ renamed[/green] [cyan]{res['old_name']}[/cyan] → "
                      f"[bold cyan]{res['name']}[/bold cyan] [dim](id unchanged: {res['id']})[/dim]")
    return 0


def cmd_campaign_archive(args: argparse.Namespace) -> int:
    """`dojo campaign archive <id>`: leave rotation, accept forgetting — a
    human decision (TTY confirms; --json is the agent relaying the learner's
    explicit ask). Git keeps the history either way."""
    api = DojoAPI(_db_path(args))
    if not _use_json(args):
        from .interactive import confirm

        camp = api.store.campaigns.get(args.campaign_id)
        if camp is None:
            raise SystemExit(f"error: campaign {args.campaign_id} not found")
        if not confirm(
            f"Archive [cyan]{camp.name}[/cyan]? Reviews stop; forgetting begins. ",
            default=False,
        ):
            console.print("[dim]kept — nothing changed[/dim]")
            return 0
    try:
        res = api.campaign_archive(args.campaign_id)
    except ValueError as exc:
        raise SystemExit(f"error: {exc}")
    if _use_json(args):
        _print_json({"ok": True, **res})
    else:
        console.print(f"[green]✓ archived[/green] — {res['next']}")
    return 0


def cmd_campaign_boost(args: argparse.Namespace) -> int:
    """Cross-campaign surfacing: 'I want THIS CAMPAIGN to come up more/less'."""
    api = DojoAPI(_db_path(args))
    campaign = api.store.campaigns.get(args.campaign_id)
    if campaign is None:
        raise SystemExit(f"error: campaign {args.campaign_id} not found")
    campaign.strategy_profile["priority_weight"] = args.factor
    api.store.campaigns.save(campaign)
    _print_json({
        "ok": True, "campaign_id": campaign.id, "priority_weight": args.factor,
        "effect": f"this campaign now surfaces with x{args.factor:g} priority in daily packets",
    })
    return 0


def cmd_topic_boost(args: argparse.Namespace) -> int:
    """Intra-campaign emphasis: 'I want exercises about THIS TOPIC more often'."""
    api = DojoAPI(_db_path(args))
    campaign = api.store.campaigns.get(args.campaign_id)
    if campaign is None:
        raise SystemExit(f"error: campaign {args.campaign_id} not found")
    entry = next((t for t in campaign.topics if t.get("path") == args.topic_path), None)
    if entry is None:
        entry = {"path": args.topic_path, "kind": args.kind or "recall", "summary": ""}
        campaign.topics.append(entry)
    entry["emphasis"] = args.factor
    api.store.campaigns.save(campaign)
    _print_json({
        "ok": True, "campaign_id": campaign.id, "topic_path": args.topic_path,
        "emphasis": args.factor,
        "effect": f"items on this topic come due x{args.factor:g} faster and win packet ties",
    })
    return 0


def build_parser() -> argparse.ArgumentParser:
    """The full argparse tree; every subcommand binds func= to its handler."""
    parser = argparse.ArgumentParser(prog="dojo")
    parser.add_argument("--db", help="Dojo root directory (backward compatible option name)")
    parser.add_argument("--json", action="store_true", help="output structured JSON instead of human-friendly text")
    parser.add_argument("--no-input", action="store_true", help="disable all interactive prompts")
    sub = parser.add_subparsers(dest="command", required=True)

    # One display contract for every practice-bearing command (owner directive
    # 2026-07-17: the screen/transcript choice is app-wide, not per-command).
    display = argparse.ArgumentParser(add_help=False)
    display.add_argument("--screen", action="store_true",
                         help="full-screen session view for this run (default: ui.mode config, else transcript)")
    display.add_argument("--transcript", action="store_true",
                         help="classic scrollback view for this run, overriding ui.mode")

    p_export = sub.add_parser("export", help="write your entire store as a fresh markdown store at a destination (backend-blind)")
    p_export.add_argument("destination", help="empty or nonexistent directory to export into")
    p_export.set_defaults(func=cmd_export)

    p_uninstall = sub.add_parser("uninstall", help="remove the skill from an agent (or --self for the program); learning data is never touched")
    p_uninstall.add_argument("agent", nargs="?", help="agent name whose skill install to remove")
    p_uninstall.add_argument("--dest", help="explicit skill directory to remove")
    p_uninstall.add_argument("--yes", action="store_true",
                             help="skip the confirmation prompt (--self)")
    p_uninstall.add_argument("--self", dest="self_uninstall", action="store_true",
                             help="show how to remove the dojo program itself (pipx/venv/binary aware)")
    p_uninstall.set_defaults(func=cmd_uninstall)

    p_bench = sub.add_parser(
        "benchmark",
        help="benchmark a model pair on dojo's pedagogy corpus (compliance + judged quality)",
    )
    p_bench.add_argument(
        "--driver", "-d", required=True,
        help='the model under test, e.g. "codex exec" or "ollama run llama3" (prompt on stdin). '
             'Distinct from fulfiller.command, which serves production tasks.',
    )
    p_bench.add_argument(
        "--judge", "-j",
        help="evaluator command grading output quality (default: benchmark.judge config if set, else --driver)",
    )
    p_bench.add_argument("--tier", choices=["all", "compliance", "quality"], default="all")
    p_bench.add_argument("--skill", action="store_true",
                         help="benchmark the DRIVER axis in isolation: can this agent "
                              "execute dojo workflows through SKILL.md? (-d is the agent "
                              "command; outcome checks, no judge spend)")
    p_bench.add_argument("--holdout", action="store_true",
                         help="release gate: run the HOLDOUT corpus and print the aggregate "
                              "only — per-scenario data is never surfaced (anti-reward-hacking)")
    p_bench.add_argument("--detail", action="store_true", help="show per-scenario criterion verdicts")
    p_bench.add_argument("--timeout", type=int, default=300)
    p_bench.add_argument("--output", "-o", help="report JSON path (default: ./dojo-benchmark-<pair>-<ts>.json)")
    p_bench.set_defaults(func=cmd_benchmark)

    p_task = sub.add_parser("task", help="the AI task queue (ADR 010)")
    p_task_sub = p_task.add_subparsers(dest="task_command", required=True)
    p_task_list = p_task_sub.add_parser("list")
    p_task_list.add_argument("--status", choices=["pending", "fulfilled", "failed"])
    p_task_list.set_defaults(func=cmd_task_list)
    p_task_show = p_task_sub.add_parser("show")
    p_task_show.add_argument("task_id")
    p_task_show.add_argument("--prompt", action="store_true", help="print only the prompt body")
    p_task_show.add_argument("--trace", action="store_true",
                             help="the submission history: the model's own words, accepted and rejected")
    p_task_show.set_defaults(func=cmd_task_show)
    p_task_submit = p_task_sub.add_parser("submit")
    p_task_submit.add_argument("task_id")
    p_task_submit.add_argument("--file", help="read the result JSON from a file instead of stdin")
    p_task_submit.set_defaults(func=cmd_task_submit)
    p_task_run = p_task_sub.add_parser("run")
    p_task_run.add_argument("--command", help="model command (default: model.command config, fulfiller.command honored)")
    p_task_run.add_argument("--limit", type=int)
    p_task_run.add_argument("--timeout", type=int, default=300)
    p_task_run.set_defaults(func=cmd_task_run)

    p_add = sub.add_parser("add")
    p_add.add_argument("path", nargs="?")
    p_add.add_argument("--text")
    p_add.add_argument("--title")
    p_add.add_argument("--topic")
    p_add.add_argument("--mission")
    p_add.add_argument("--locator", help="The locator URL or path representing where this text originated")
    p_add.add_argument("--generate", action="store_true")
    p_add.set_defaults(func=cmd_add)

    p_source = sub.add_parser("source")
    p_source_sub = p_source.add_subparsers(dest="source_command", required=True)

    p_src_list = p_source_sub.add_parser("list")
    p_src_list.set_defaults(func=cmd_source_list)

    p_src_show = p_source_sub.add_parser("show")
    p_src_show.add_argument("name")
    p_src_show.add_argument("--start-line", type=int)
    p_src_show.add_argument("--end-line", type=int)
    p_src_show.set_defaults(func=cmd_source_show)

    p_src_topics = p_source_sub.add_parser("topics")
    p_src_topics.add_argument("name")
    p_src_topics.set_defaults(func=cmd_source_topics)

    p_src_candidates = p_source_sub.add_parser("candidates")
    p_src_candidates.add_argument("name")
    p_src_candidates.add_argument("--topic")
    p_src_candidates.set_defaults(func=cmd_source_candidates)

    p_src_review = p_source_sub.add_parser("review")
    p_src_review.add_argument("name")
    p_src_review.set_defaults(func=cmd_source_review)

    p_queue = sub.add_parser("queue")
    p_queue.add_argument("item", nargs="?")
    p_queue.add_argument("--source")
    p_queue.add_argument("--topic")
    p_queue.add_argument("--limit", type=int)
    p_queue.set_defaults(func=cmd_queue)

    p_start = sub.add_parser("start")
    p_start.add_argument("--topic")
    p_start.add_argument("--limit", type=int, default=5)
    p_start.add_argument("--reset", action="store_true")
    p_start.set_defaults(func=cmd_start)

    p_ready = sub.add_parser("ready")
    p_ready.add_argument("--session")
    p_ready.set_defaults(func=cmd_ready)

    p_reveal = sub.add_parser("reveal")
    p_reveal.add_argument("--session")
    p_reveal.set_defaults(func=cmd_ready)

    p_answer = sub.add_parser("answer")
    p_answer.add_argument("response")
    p_answer.add_argument("--session")
    p_answer.set_defaults(func=cmd_answer)

    p_progress = sub.add_parser("progress")
    p_progress.set_defaults(func=cmd_progress)

    p_doctor = sub.add_parser("doctor")
    p_doctor.set_defaults(func=cmd_doctor)

    p_install = sub.add_parser("install")
    p_install.add_argument("agent", nargs="?")
    p_install.add_argument("--dest", "-d", help="Custom destination directory to install the Dojo skill into")
    p_install.add_argument("--argv", help="Command-line arguments to invoke the agent for AI requests")
    p_install.add_argument("--force", "-f", action="store_true", help="Force installation and overwrite target path even if not owned by Dojo")
    p_install.set_defaults(func=cmd_install)

    p_due = sub.add_parser("due")
    p_due.add_argument("--topic")
    p_due.set_defaults(func=cmd_due)

    p_skip = sub.add_parser("skip")
    p_skip.add_argument("--reason", default="forgot", choices=["forgot", "too_easy", "too_hard", "bad_quality"])
    p_skip.add_argument("--feedback")
    p_skip.add_argument("--session")
    p_skip.set_defaults(func=cmd_skip)

    p_correct = sub.add_parser("correct")
    p_correct.add_argument("--feedback")
    p_correct.add_argument("--score", type=float, default=1.0)
    p_correct.set_defaults(func=cmd_correct)

    p_feedback = sub.add_parser("feedback")
    p_feedback.add_argument("comment")
    p_feedback.add_argument("--campaign")
    p_feedback.set_defaults(func=cmd_feedback)

    p_admin = sub.add_parser("admin")
    p_admin_sub = p_admin.add_subparsers(dest="admin_command", required=True)
    p_consolidate = p_admin_sub.add_parser("consolidate")
    p_consolidate.add_argument("--campaign")
    p_consolidate.set_defaults(func=cmd_admin_consolidate)

    p_config = sub.add_parser("config")
    p_config_sub = p_config.add_subparsers(dest="config_command", required=True)
    p_config_set = p_config_sub.add_parser("set")
    p_config_set.add_argument("key")
    p_config_set.add_argument("value")
    p_config_set.set_defaults(func=cmd_config_set)
    p_config_show = p_config_sub.add_parser("show")
    p_config_show.set_defaults(func=cmd_config_show)

    p_stats = sub.add_parser("stats", help="retention, atrophy, and AI token spend — computed, estimates tagged")
    p_stats.set_defaults(func=cmd_stats)

    p_capture = sub.add_parser("capture", help="save something you just learned — one utterance now, filed into a campaign later")
    p_capture.add_argument("text", help="the thing to remember, as text (agents: fetch/summarize links yourself)")
    p_capture.add_argument("--why", help="optional: why this matters to you, in your words")
    p_capture.add_argument("--locator", help="optional: where it came from (URL or file path), kept as provenance")
    p_capture.set_defaults(func=cmd_capture)

    p_inbox = sub.add_parser("inbox", help="captures awaiting a home; confirm or dismiss proposed routes")
    p_inbox_sub = p_inbox.add_subparsers(dest="inbox_command")
    p_inbox.set_defaults(func=cmd_inbox)
    p_inbox_confirm = p_inbox_sub.add_parser("confirm")
    p_inbox_confirm.add_argument("capture_id")
    p_inbox_confirm.set_defaults(func=cmd_inbox)
    p_inbox_dismiss = p_inbox_sub.add_parser("dismiss")
    p_inbox_dismiss.add_argument("capture_id")
    p_inbox_dismiss.set_defaults(func=cmd_inbox)

    p_reflect = sub.add_parser("reflect", help="distill recent evidence into insights and strategy (emits a reflection task)")
    p_reflect.add_argument("--campaign")
    p_reflect.set_defaults(func=cmd_admin_consolidate)

    p_daily = sub.add_parser("daily", parents=[display],
                             help="build today's bounded, explained practice packet")
    p_daily.add_argument("--size", type=int, help="override daily.packet_size (hard cap 8)")
    p_daily.add_argument("--reset", action="store_true", help="discard the active session and rebuild")
    p_daily.set_defaults(func=cmd_daily)

    p_why = sub.add_parser("why", help="explain every scheduling choice behind the current packet")
    p_why.set_defaults(func=cmd_why)

    p_more = sub.add_parser(
        "more", parents=[display],
        help="ask for a bounded extra-practice top-up — granted only when your "
             "7-day review budget agrees; refusals show the projection",
    )
    p_more.add_argument("--force", action="store_true",
                        help="override the debt guard (the projection still prints); the once-per-day cap stays")
    p_more.set_defaults(func=cmd_more)

    p_learn = sub.add_parser(
        "learn", parents=[display],
        help="'I want to learn X' — routes the goal against your campaigns first "
             "(extend a near fit, or plan fresh); resolve a routed goal with "
             "`learn extend <task-id>` / `learn new <task-id>`",
    )
    p_learn.add_argument(
        "goal", nargs="+",
        help="the goal, verbatim — or a verb (extend|new) followed by a goal-route task id",
    )
    p_learn.add_argument("--new", action="store_true",
                         help="skip routing; plan a new campaign directly")
    p_learn.set_defaults(func=cmd_learn)

    p_plan = sub.add_parser("plan", help="your authority over AI-proposed plan changes: show, confirm, reject, revert")
    p_plan_sub = p_plan.add_subparsers(dest="plan_command")
    p_plan.set_defaults(func=cmd_plan)
    for verb, blurb in (
        ("show", "current plan + any pending proposed restructure"),
        ("confirm", "accept the pending proposal (it becomes the confirmed baseline)"),
        ("reject", "decline the pending proposal; nothing changes"),
        ("revert", "undo the last auto-applied plan change"),
    ):
        p_verb = p_plan_sub.add_parser(verb, help=blurb)
        p_verb.add_argument("--campaign", help="campaign id (optional when unambiguous)")
        p_verb.set_defaults(func=cmd_plan)

    p_insights = sub.add_parser(
        "insights",
        help="the learner model, with receipts: see every belief, trace it to "
             "your verbatim answers, contest it in your own words",
    )
    p_insights.add_argument("--campaign", help="limit to one campaign")
    p_insights.add_argument("--all", action="store_true",
                            help="include resolved insights (what you overcame)")
    p_insights_sub = p_insights.add_subparsers(dest="insights_command")
    p_insights.set_defaults(func=cmd_insights)
    p_ins_show = p_insights_sub.add_parser("show", help="the receipts card: every answer behind a belief + its effect")
    p_ins_show.add_argument("insight_id")
    p_ins_show.set_defaults(func=cmd_insights)
    p_ins_resolve = p_insights_sub.add_parser("resolve", help="contest a belief — your words outrank the evidence")
    p_ins_resolve.add_argument("insight_id")
    p_ins_resolve.add_argument("--because", required=True, help="your reason, verbatim — it feeds the next reflection")
    p_ins_resolve.set_defaults(func=cmd_insights)

    p_amend = sub.add_parser(
        "amend",
        help="replace a previous answer while its grade is pending "
             "(in-session: /back; landed grades: dojo correct)",
    )
    p_amend.add_argument("answer")
    p_amend.add_argument("--back", type=int, default=1,
                         help="how many questions back (default 1)")
    p_amend.set_defaults(func=cmd_amend)

    p_topic = sub.add_parser(
        "topic",
        help="care-exit for single topics: retire stops its reviews (noise, "
             "not diligence, once you stop caring); revive resumes them",
    )
    p_topic_sub = p_topic.add_subparsers(dest="topic_command", required=True)
    p_topic_retire = p_topic_sub.add_parser("retire", help="stop this topic's reviews (reversible)")
    p_topic_retire.add_argument("path")
    p_topic_retire.add_argument("--because", default="", help="your reason, kept verbatim")
    p_topic_retire.add_argument("--campaign", default=None)
    p_topic_retire.set_defaults(func=cmd_topic_retire)
    p_topic_revive = p_topic_sub.add_parser("revive", help="resume a retired topic's reviews")
    p_topic_revive.add_argument("path")
    p_topic_revive.add_argument("--campaign", default=None)
    p_topic_revive.set_defaults(func=cmd_topic_revive)

    p_campaign = sub.add_parser("campaign")
    p_camp_sub = p_campaign.add_subparsers(dest="campaign_command", required=True)

    p_camp_list = p_camp_sub.add_parser("list", help="every campaign: status, phase, retention, dues, idle days")
    p_camp_list.set_defaults(func=cmd_campaign_list)

    p_camp_archive = p_camp_sub.add_parser("archive", help="leave rotation, accept forgetting (git keeps history)")
    p_camp_archive.add_argument("campaign_id")
    p_camp_archive.set_defaults(func=cmd_campaign_archive)

    p_camp_rename = p_camp_sub.add_parser("rename", help="fix a campaign's display name in place (id and history stay)")
    p_camp_rename.add_argument("campaign_id")
    p_camp_rename.add_argument("name")
    p_camp_rename.set_defaults(func=cmd_campaign_rename)

    p_camp_boost = p_camp_sub.add_parser("boost", help="surface this CAMPAIGN more (or less) in daily packets")
    p_camp_boost.add_argument("campaign_id")
    p_camp_boost.add_argument("factor", type=float, help="1.0 = neutral, 2.0 = twice the priority, 0.5 = half")
    p_camp_boost.set_defaults(func=cmd_campaign_boost)

    p_topic_boost = p_camp_sub.add_parser("topic-boost", help="practice this TOPIC more often within its campaign")
    p_topic_boost.add_argument("campaign_id")
    p_topic_boost.add_argument("topic_path")
    p_topic_boost.add_argument("factor", type=float, help="2.0 = due twice as fast")
    p_topic_boost.add_argument("--kind", choices=["recall", "skill"], help="lane when creating a new topic entry")
    p_topic_boost.set_defaults(func=cmd_topic_boost)

    p_camp_plan = p_camp_sub.add_parser("plan", parents=[display])
    p_camp_plan.add_argument("goal", help="The user's high-level learning goal or target skill")
    p_camp_plan.add_argument("--level", "-l", choices=["beginner", "intermediate", "advanced"])
    p_camp_plan.add_argument("--context", "-c", help="Constraints, deadlines, exclusions, preferences")
    p_camp_plan.set_defaults(func=cmd_campaign_plan)

    p_camp_create = p_camp_sub.add_parser("create")
    p_camp_create.add_argument("goal", nargs="?", help="The user's high-level learning goal or target skill")
    p_camp_create.add_argument("--from-task", dest="from_task", help="Materialize a fulfilled campaign.plan task")
    p_camp_create.add_argument("--into", help="Apply the plan onto an existing BARE campaign (capture-born) instead of creating one")
    p_camp_create.add_argument("--level", "-l", default="intermediate", choices=["beginner", "intermediate", "advanced"], help="Initial comfort level")
    p_camp_create.add_argument("--name", "-n", help="Optional override for the campaign name")
    p_camp_create.add_argument("--exclude", "-e", help="Optional skills or areas to defer/exclude")
    p_camp_create.add_argument("--feedback", "-f", help="Refinement answers or feedback to customize target scope")
    p_camp_create.add_argument("--source", "-s", help="Optional source file path, URL, or raw text to attach to the campaign")
    p_camp_create.set_defaults(func=cmd_campaign_create)

    p_camp_link = p_camp_sub.add_parser("link")
    p_camp_link.add_argument("campaign_id", help="The campaign ID to link to")
    p_camp_link.add_argument("source_id", help="The source ID to link")
    p_camp_link.add_argument("--purpose", "-p", help="Why this source is linked to this campaign")
    p_camp_link.set_defaults(func=cmd_campaign_link)

    p_camp_history = p_camp_sub.add_parser("history")
    p_camp_history.add_argument("--campaign", help="Optional campaign ID (default: latest)")
    p_camp_history.add_argument("--show-snapshots", action="store_true", help="Include full attack plan JSON snapshots in history details")
    p_camp_history.set_defaults(func=cmd_campaign_history)

    p_camp_export = p_camp_sub.add_parser("export")
    p_camp_export.add_argument("campaign", nargs="?", default="latest", help="The campaign ID to export (default: latest)")
    p_camp_export.add_argument("--format", "-f", default="pdf", choices=["pdf", "markdown"], help="Format to export (default: pdf)")
    p_camp_export.add_argument("--output", "-o", help="Custom output file path. Defaults to <campaign_slug>_syllabus.<ext> in current directory.")
    p_camp_export.set_defaults(func=cmd_campaign_export)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Console entry point: dispatch the handler, then write one git
    recovery point on success (`_audit_command_boundary`)."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        rc = args.func(args)
    except (KeyboardInterrupt, EOFError):
        # TUI manners (owner field report 2026-07-09): a cancel is a cancel,
        # never a stack trace.
        print()
        console.print("[dim]cancelled[/dim]")
        return 130
    if rc == 0:
        _audit_command_boundary(args, argv)
    return rc


def _audit_command_boundary(args: argparse.Namespace, argv: list[str] | None) -> None:
    """One recovery point per successful CLI command (ADR 011).

    Entity writes never auto-commit; this is the only place command-level
    batching happens. A no-op when the command changed nothing. Failures are
    non-fatal here — the doctor surfaces unhealthy audit state instead.
    """
    try:
        from .store import DojoStore

        words = argv if argv is not None else sys.argv[1:]
        summary = " ".join(str(w) for w in words[:6])
        DojoStore(_db_path(args)).audit(f"dojo {summary}")
    except Exception:
        pass


if __name__ == "__main__":
    raise SystemExit(main())
