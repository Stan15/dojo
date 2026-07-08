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
    if getattr(args, "json", False):
        return True
    if not sys.stdout.isatty():
        return True
    return False


def _db_path(args: argparse.Namespace) -> Path | None:
    return Path(args.db) if getattr(args, "db", None) else None


def _print_json(value: Any) -> None:
    print(json.dumps(value, sort_keys=True))



def cmd_add(args: argparse.Namespace) -> int:
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

    if hasattr(sys, "_MEIPASS"):
        repo_skills_dojo = Path(getattr(sys, "_MEIPASS")) / "skills" / "dojo"
    else:
        repo_skills_dojo = Path(__file__).resolve().parent.parent.parent / "skills" / "dojo"

    if not repo_skills_dojo.exists():
        raise SystemExit(f"error: skills/dojo directory not found at {repo_skills_dojo}")

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
        shutil.copytree(repo_skills_dojo, target_path)
    except Exception as exc:
        raise SystemExit(f"error: failed to install dojo skill to {target_path}: {exc}")

    store = DojoStore(_db_path(args))

    # Harness agents need nothing beyond the skill: they fulfill tasks
    # themselves (ADR 010). An optional one-string fulfiller command enables
    # headless use (dojo task run) — no wrapper scripts, ever (Q1).
    fulfiller = getattr(args, "argv", None)
    if fulfiller:
        store.configs.set("fulfiller.command", fulfiller)

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


def cmd_doctor(args: argparse.Namespace) -> int:
    store = DojoStore(_db_path(args))
    results = store.doctor.run()
    
    # Flatten all errors to see if there are any failures
    all_errors = [err for errs in results.values() for err in errs]
        
    if _use_json(args):
        _print_json({
            "ok": len(all_errors) == 0,
            "results": results,
            "errors": all_errors
        })
    else:
        console.print("[bold cyan]Dojo Doctor Diagnostics[/bold cyan]")
        console.print("=======================")
        for category, errors in results.items():
            if not errors:
                console.print(f"[green]✓[/green] [bold]{category}[/bold]")
            else:
                console.print(f"[red]✗[/red] [bold]{category}[/bold]")
                for err in errors:
                    console.print(f"    - [red]{err}[/red]")
        console.print("")
        
        if all_errors:
            console.print(f"[bold red]✗ Dojo Doctor found {len(all_errors)} issues in your repository.[/bold red]")
        else:
            if not store.dojo_dir.exists():
                console.print("[bold green]✓ Dojo Doctor: Repository directory does not exist yet (will be initialized on first run). Folder is clear![/bold green]")
            else:
                console.print("[bold green]✓ Dojo Doctor: Repository directory is completely compliant and clean![/bold green]")
                
    return 1 if all_errors else 0


def cmd_due(args: argparse.Namespace) -> int:
    api = DojoAPI(_db_path(args))
    count = api.get_due_count(topic=args.topic)
    if _use_json(args):
        _print_json({"due_count": count})
    else:
        console.print(f"You have [bold cyan]{count}[/bold cyan] exercises due.")
    return 0


def cmd_skip(args: argparse.Namespace) -> int:
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
    api = DojoAPI(_db_path(args))
    res = api.save_config(args.key, args.value)
    if _use_json(args):
        _print_json(res)
    else:
        console.print(f"[bold green]Config set successfully:[/bold green] [cyan]{args.key}[/cyan] = [green]{args.value}[/green]")
    return 0


def cmd_config_show(args: argparse.Namespace) -> int:
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


def cmd_campaign_plan(args: argparse.Namespace) -> int:
    """Emits a campaign.plan task (ADR 010). The fulfilled task carries the
    proposal (mission/topics/phases/refinement questions); materialize it with:
    dojo campaign create --from-task <task-id>."""
    from .store import DojoStore
    from .tasks import flows

    store = DojoStore(_db_path(args))
    existing = sorted({
        ex.topic_path
        for camp in store.campaigns.list()
        for ex in store.exercises.list(camp.id)
    } | {
        camp.topic_path for camp in store.campaigns.list() if camp.topic_path
    })
    notes = []
    if getattr(args, "level", None):
        notes.append(f"level: {args.level}")
    if getattr(args, "context", None):
        notes.append(args.context)
    task = flows.request_plan(
        store,
        goal=args.goal,
        context_notes="; ".join(notes),
        existing_topics="\n".join(existing),
    )
    _print_json({
        "ok": True,
        "task": flows.task_ref(task),
        "next": (
            f"fulfill the task (dojo task show {task.id} --prompt → produce the JSON → "
            f"dojo task submit {task.id}); review the proposal and its refinement_questions "
            f"with the learner, then: dojo campaign create --from-task {task.id} "
            f"[--name <override>]"
        ),
    })
    return 0


def _materialize_campaign_from_task(args: argparse.Namespace) -> int:
    """Deterministic creation from a fulfilled campaign.plan task (I2:
    review-before-trust — the human said yes before this runs)."""
    from .store import DojoStore

    api = DojoAPI(_db_path(args))
    task = api.store.tasks.get(args.from_task)
    if task is None or task.kind != "campaign.plan":
        raise SystemExit(f"error: {args.from_task} is not a campaign.plan task")
    if task.status != "fulfilled":
        raise SystemExit(f"error: task {args.from_task} is {task.status}, not fulfilled")
    proposal = (task.context or {}).get("_applied")
    if not proposal:
        raise SystemExit(f"error: task {args.from_task} carries no applied proposal")

    topic_paths = [t["path"] for t in proposal["topics"]]
    root = topic_paths[0].split(".")[0] if topic_paths else "general"
    name = args.name or task.context.get("goal") or root

    res = api.create_campaign(
        name=name,
        topic_path=root,
        mission=proposal["mission"],
    )
    campaign = api.store.campaigns.get(res["id"])
    campaign.attack_plan = [AttackPlanPhase.model_validate(p) for p in proposal["phases"]]
    # Topic kinds (recall vs skill) ride along for the M3 scheduler.
    campaign.topics = proposal["topics"]
    lines = [f"# {name}", "", proposal["mission"], ""]
    for t in proposal["topics"]:
        lines.append(f"- `{t['path']}` ({t['kind']}): {t.get('summary', '')}")
    campaign.syllabus_markdown = "\n".join(lines)
    api.store.campaigns.save(campaign)

    _print_json({
        "ok": True,
        "type": "campaign_created",
        "data": api.store.campaigns.get(res["id"]).model_dump(),
        "refinement_questions": proposal.get("refinement_questions", []),
        "next": "run dojo start to begin practicing",
    })
    return 0


def cmd_campaign_create(args: argparse.Namespace) -> int:
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

        # 2. Derive topic path
        temp_slug = "".join(c for c in args.goal.lower() if c.isalnum() or c == " ").strip().replace(" ", ".")[:25]
        if not temp_slug:
            temp_slug = f"topic_{uuid.uuid4().hex[:8]}"

        # 3. Create campaign
        res = api.create_campaign(
            name=args.name or f"Learning Campaign: {args.goal}",
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
                    "  Fulfill the task(s) (or configure one: dojo config set fulfiller.command \"<cmd>\" "
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
            _print_json({
                "ok": True,
                "type": "campaign_created",
                "data": res,
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
    from .store import DojoStore

    store = DojoStore(_db_path(args))
    task = store.tasks.get(args.task_id)
    if task is None:
        _print_json({"ok": False, "error": f"no such task: {args.task_id}"})
        return 1
    if args.prompt:
        print(task.prompt)
        return 0
    _print_json({**task.model_dump(exclude={"prompt"}), "prompt": task.prompt})
    return 0


def cmd_task_submit(args: argparse.Namespace) -> int:
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
    command = args.command or store.configs.get_value("fulfiller.command")
    if not command:
        _print_json({
            "ok": False,
            "error": "no fulfiller command: pass --command or set `dojo config set fulfiller.command \"<cmd>\"`",
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


def cmd_export(args: argparse.Namespace) -> int:
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
        exe = Path(sys.executable).resolve()
        home = Path.home()
        if getattr(sys, "frozen", False):
            method = ("binary", f"rm {Path(sys.argv[0]).resolve()}")
        elif "pipx" in str(exe):
            method = ("pipx", "pipx uninstall dojo")
        elif str(exe).startswith(str(home / ".dojo" / "venv")):
            method = ("venv", f"rm -rf {home / '.dojo'} {home / '.local/bin/dojo'}")
        else:
            method = ("pip", f"{exe} -m pip uninstall dojo")
        _print_json({
            "ok": True,
            "install_method": method[0],
            "run_this": method[1],
            "learning_data": str(DEFAULT_DOJO_DIR),
            "note": "your learning data is untouched; delete it manually only if you "
                    "are sure — it is your entire practice history",
        })
        return 0

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

    if not target_path.exists():
        _print_json({"ok": True, "removed": [], "note": f"nothing installed at {target_path}"})
        return 0
    if not _is_owned_by_dojo(target_path):
        _print_json({
            "ok": False,
            "error": f"{target_path} exists but is not a dojo-owned skill "
                     "(no dojo owner marker in SKILL.md) — refusing to delete it",
        })
        return 1
    _shutil.rmtree(target_path)
    removed.append(str(target_path))
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

    from .evals.runner import run_benchmark

    driver = args.fulfiller
    judge = args.judge or driver
    tiers = ("compliance",) if args.tier == "compliance" else (
        ("quality",) if args.tier == "quality" else ("compliance", "quality")
    )

    if not _use_json(args):
        console.print("\n[bold]🥋 Dojo model benchmark[/bold]")
        console.print(f"  Driver (does the work):   [cyan]{driver}[/cyan]")
        console.print(f"  Judge  (grades quality):  [cyan]{judge}[/cyan]")
        console.print("  [dim]This drives your models on real scenarios — expect several minutes.[/dim]\n")

    def progress(msg: str) -> None:
        if not _use_json(args):
            console.print(f"  [dim]·[/dim] {msg}")

    with tempfile.TemporaryDirectory(prefix="dojo-bench-") as workdir:
        report = run_benchmark(
            driver=driver, judge=judge, workdir=Path(workdir),
            timeout=args.timeout, tiers=tiers, progress=progress,
        )

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


def cmd_capture(args: argparse.Namespace) -> int:
    api = DojoAPI(_db_path(args))
    res = api.capture(args.text, why=args.why)
    _print_json({"ok": True, **res})
    return 0


def cmd_inbox(args: argparse.Namespace) -> int:
    api = DojoAPI(_db_path(args))
    if args.inbox_command == "confirm":
        _print_json({"ok": True, **api.inbox_confirm(args.capture_id)})
    elif args.inbox_command == "dismiss":
        _print_json({"ok": True, **api.inbox_dismiss(args.capture_id)})
    else:
        _print_json({"ok": True, **api.inbox()})
    return 0


def cmd_daily(args: argparse.Namespace) -> int:
    api = DojoAPI(_db_path(args))
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


def cmd_why(args: argparse.Namespace) -> int:
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
    parser = argparse.ArgumentParser(prog="dojo")
    parser.add_argument("--db", help="Dojo root directory (backward compatible option name)")
    parser.add_argument("--json", action="store_true", help="output structured JSON instead of human-friendly text")
    parser.add_argument("--no-input", action="store_true", help="disable all interactive prompts")
    sub = parser.add_subparsers(dest="command", required=True)

    p_export = sub.add_parser("export", help="write your entire store as a fresh markdown store at a destination (backend-blind)")
    p_export.add_argument("destination", help="empty or nonexistent directory to export into")
    p_export.set_defaults(func=cmd_export)

    p_uninstall = sub.add_parser("uninstall", help="remove the skill from an agent (or --self for the program); learning data is never touched")
    p_uninstall.add_argument("agent", nargs="?", help="agent name whose skill install to remove")
    p_uninstall.add_argument("--dest", help="explicit skill directory to remove")
    p_uninstall.add_argument("--self", dest="self_uninstall", action="store_true",
                             help="show how to remove the dojo program itself (pipx/venv/binary aware)")
    p_uninstall.set_defaults(func=cmd_uninstall)

    p_bench = sub.add_parser(
        "benchmark",
        help="benchmark a model pair on dojo's pedagogy corpus (compliance + judged quality)",
    )
    p_bench.add_argument(
        "--fulfiller", "-f", required=True,
        help='driver command, e.g. "codex exec" or "ollama run llama3" (prompt on stdin)',
    )
    p_bench.add_argument(
        "--judge", "-j",
        help="evaluator command grading output quality (default: same as --fulfiller)",
    )
    p_bench.add_argument("--tier", choices=["all", "compliance", "quality"], default="all")
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
    p_task_show.set_defaults(func=cmd_task_show)
    p_task_submit = p_task_sub.add_parser("submit")
    p_task_submit.add_argument("task_id")
    p_task_submit.add_argument("--file", help="read the result JSON from a file instead of stdin")
    p_task_submit.set_defaults(func=cmd_task_submit)
    p_task_run = p_task_sub.add_parser("run")
    p_task_run.add_argument("--command", help="fulfiller command (default: fulfiller.command config)")
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

    p_capture = sub.add_parser("capture", help="save something you just learned — one utterance, filed later")
    p_capture.add_argument("text", help="the thing to remember")
    p_capture.add_argument("--why", help="optional: why this matters to you")
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

    p_daily = sub.add_parser("daily", help="build today's bounded, explained practice packet")
    p_daily.add_argument("--size", type=int, help="override daily.packet_size (hard cap 8)")
    p_daily.add_argument("--reset", action="store_true", help="discard the active session and rebuild")
    p_daily.set_defaults(func=cmd_daily)

    p_why = sub.add_parser("why", help="explain every scheduling choice behind the current packet")
    p_why.set_defaults(func=cmd_why)

    p_campaign = sub.add_parser("campaign")
    p_camp_sub = p_campaign.add_subparsers(dest="campaign_command", required=True)

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

    p_camp_plan = p_camp_sub.add_parser("plan")
    p_camp_plan.add_argument("goal", help="The user's high-level learning goal or target skill")
    p_camp_plan.add_argument("--level", "-l", choices=["beginner", "intermediate", "advanced"])
    p_camp_plan.add_argument("--context", "-c", help="Constraints, deadlines, exclusions, preferences")
    p_camp_plan.set_defaults(func=cmd_campaign_plan)

    p_camp_create = p_camp_sub.add_parser("create")
    p_camp_create.add_argument("goal", nargs="?", help="The user's high-level learning goal or target skill")
    p_camp_create.add_argument("--from-task", dest="from_task", help="Materialize a fulfilled campaign.plan task")
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
    parser = build_parser()
    args = parser.parse_args(argv)
    rc = args.func(args)
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
