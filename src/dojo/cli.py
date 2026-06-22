from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from pathlib import Path
from typing import Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from . import db
from . import generate
from . import connectors
from .api import DojoAPI

console = Console()
VALID_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")


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


def _validate_name(name: str) -> None:
    if not VALID_NAME.fullmatch(name):
        raise SystemExit("invalid AI connector name: use 1-64 letters, numbers, hyphen, or underscore, starting with a letter")


def _render(connector: dict[str, Any], *, next_action: str | None = None) -> dict[str, Any]:
    rendered = dict(connector)
    if next_action:
        rendered["next"] = next_action
    return rendered


def cmd_connect_ai_command(args: argparse.Namespace) -> int:
    _validate_name(args.name)
    if args.command and args.command[0] == "--":
        args.command = args.command[1:]
    elif args.command:
        raw = list(args.command)
        external: list[str] = []
        idx = 0
        while idx < len(raw):
            token = raw[idx]
            if token == "--":
                external = raw[idx + 1 :]
                break
            if token == "--default":
                args.default = True
                idx += 1
                continue
            if token == "--replace":
                args.replace = True
                idx += 1
                continue
            if token in {"--input", "--output", "--timeout"}:
                if idx + 1 >= len(raw):
                    raise SystemExit(f"{token} requires a value")
                value = raw[idx + 1]
                if token == "--input":
                    args.input = value
                elif token == "--output":
                    args.output = value
                else:
                    args.timeout = int(value)
                idx += 2
                continue
            external = raw[idx:]
            break
        args.command = external
    if not args.command:
        raise SystemExit("command connector requires argv after --")
    db.init_db(_db_path(args))
    with db.connect(_db_path(args)) as conn:
        try:
            connector = db.save_ai_connector(
                conn,
                name=args.name,
                argv=args.command,
                input_mode=args.input,
                output_mode=args.output,
                timeout_seconds=args.timeout,
                is_default=args.default,
                replace=args.replace,
            )
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
    _print_json(_render(connector, next_action=f"dojo connect ai test {connector['name']}"))
    return 0


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
            content = file_path.read_text()
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
                str(s["candidates_count"]),
                s["created_at"].split("T")[0],
            )
        console.print(table)
    return 0


def cmd_source_show(args: argparse.Namespace) -> int:
    api = DojoAPI(_db_path(args))
    source = api.get_source(
        args.name,
        start_line=getattr(args, "start_line", None),
        end_line=getattr(args, "end_line", None)
    )
    if source is None:
        raise SystemExit(f"unknown source: {args.name}")
    if _use_json(args):
        _print_json(source)
    else:
        is_sliced = getattr(args, "start_line", None) is not None or getattr(args, "end_line", None) is not None
        if is_sliced:
            content_display = source['content']
            excerpt_label = f"Content Span (lines {getattr(args, 'start_line', None) or 1} to {getattr(args, 'end_line', None) or 'end'}):"
        else:
            content_display = source['content'][:300] + '...' if len(source['content']) > 300 else source['content']
            excerpt_label = "Content Excerpt:"

        details = (
            f"[bold cyan]ID:[/bold cyan] {source['id']}\n"
            f"[bold cyan]Kind:[/bold cyan] {source['kind']}\n"
            f"[bold cyan]Path/Locator:[/bold cyan] {source['path'] or 'N/A'}\n"
            f"[bold cyan]Mission:[/bold cyan] {source['mission'] or 'None'}\n"
            f"[bold cyan]Candidates Left:[/bold cyan] {source['candidates_count']}\n"
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
            table.add_row(t["topic_path"], str(t["candidates_count"]))
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
            ans_str = c["answer"] if c["answer"] else json.dumps(c["rubric"])
            ans_short = ans_str[:40] + "..." if len(ans_str) > 40 else ans_str
            prompt_short = c["prompt"][:40] + "..." if len(c["prompt"]) > 40 else c["prompt"]
            table.add_row(
                c["id"],
                c["topic_path"],
                prompt_short,
                ans_short,
                c["difficulty"] or "N/A",
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
            f"[bold cyan]Answer:[/bold cyan] {c['answer'] or 'N/A'}\n"
            f"[bold cyan]Rubric:[/bold cyan] {json.dumps(c['rubric']) if c['rubric'] else 'None'}"
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
                f"Answer: {c['answer'] or ''}\n"
            )

            with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w+") as tf:
                tf.write(content_template)
                temp_name = tf.name

            try:
                subprocess.run([editor, temp_name], check=True)
                updated = Path(temp_name).read_text()

                lines = updated.splitlines()
                new_topic = c["topic_path"]
                new_prompt = c["prompt"]
                new_answer = c["answer"]

                for line in lines:
                    if line.startswith("Topic Path:"):
                        new_topic = line.split("Topic Path:", 1)[-1].strip()
                    elif line.startswith("Prompt:"):
                        new_prompt = line.split("Prompt:", 1)[-1].strip()
                    elif line.startswith("Answer:"):
                        new_answer = line.split("Answer:", 1)[-1].strip()

                api.save_candidate(
                    id=c["id"],
                    source_id=c["source_id"],
                    prompt=new_prompt,
                    answer=new_answer,
                    rubric=c["rubric"],
                    topic_path=new_topic,
                    source_refs=c["source_refs"],
                    difficulty=c["difficulty"],
                    generation_run_id=c["generation_run_id"],
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
        promoted_exercises = api.promote_source_topic(source_id, topic_path=args.topic, limit=args.limit)
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


def cmd_connect_ai_list(args: argparse.Namespace) -> int:
    db.init_db(_db_path(args))
    with db.connect(_db_path(args)) as conn:
        _print_json(db.list_ai_connectors(conn))
    return 0


def cmd_connect_ai_show(args: argparse.Namespace) -> int:
    db.init_db(_db_path(args))
    with db.connect(_db_path(args)) as conn:
        connector = db.get_ai_connector(conn, args.name)
    if connector is None:
        raise SystemExit(f"unknown AI connector: {args.name}")
    _print_json(_render(connector, next_action=f"dojo connect ai test {connector['name']}"))
    return 0


def cmd_connect_ai_use(args: argparse.Namespace) -> int:
    db.init_db(_db_path(args))
    with db.connect(_db_path(args)) as conn:
        try:
            connector = db.set_default_ai_connector(conn, args.name)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
    _print_json(_render(connector, next_action=f"dojo connect ai test {connector['name']}"))
    return 0


def cmd_connect_ai_remove(args: argparse.Namespace) -> int:
    db.init_db(_db_path(args))
    with db.connect(_db_path(args)) as conn:
        try:
            removed = db.remove_ai_connector(conn, args.name, force=args.force)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
    _print_json({"removed": removed["name"], "was_default": removed["is_default"]})
    return 0


def cmd_connect_ai_test(args: argparse.Namespace) -> int:
    from datetime import datetime, timezone
    db.init_db(_db_path(args))
    with db.connect(_db_path(args)) as session:
        connector_name = args.name
        if not connector_name:
            default_conn = connectors._default_connector(session)
            if not default_conn:
                raise SystemExit("no default AI connector configured")
            connector_name = default_conn["name"]

        connector = db.get_ai_connector(session, connector_name)
        if connector is None:
            raise SystemExit(f"unknown AI connector: {connector_name}")

        request = {
            "task": "smoke.test",
            "version": 1,
            "prompt": "Hello! Reply with OK if you receive this."
        }

        result = connectors.invoke_command_connector(_db_path(args), request, connector_name=connector_name)

        if result.status == "ok":
            summary = f"Success (duration: {result.duration_seconds:.2f}s)"
        else:
            summary = f"Failed: {result.error or 'unknown error'}"

        db.update_connector_test_result(session, connector_name, result.status, summary)

        output_data = {
            "connector_name": connector_name,
            "status": result.status,
            "duration_seconds": result.duration_seconds,
            "parse_status": result.parse_status,
            "exit_code": result.exit_code,
            "stdout": result.raw_stdout,
            "stderr": result.raw_stderr,
            "error": result.error,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        if _use_json(args):
            _print_json(output_data)
        else:
            if result.status == "ok":
                status_str = f"[bold green]SUCCESS[/bold green] (duration: {result.duration_seconds:.2f}s)"
                details = (
                    f"[bold cyan]Connector Name:[/bold cyan] {connector_name}\n"
                    f"[bold cyan]Status:[/bold cyan] {status_str}\n"
                    f"[bold cyan]Exit Code:[/bold cyan] {result.exit_code}\n"
                    f"[bold cyan]Timestamp:[/bold cyan] {output_data['timestamp']}\n\n"
                    f"[bold cyan]Stdout Excerpt:[/bold cyan]\n"
                    f"{result.raw_stdout[:500] + '...' if len(result.raw_stdout) > 500 else result.raw_stdout}"
                )
                console.print(Panel(details, title="[bold green]AI Connector Test: OK[/bold green]", expand=False))
            else:
                status_str = f"[bold red]FAILED[/bold red] (duration: {result.duration_seconds:.2f}s)"
                details = (
                    f"[bold cyan]Connector Name:[/bold cyan] {connector_name}\n"
                    f"[bold cyan]Status:[/bold cyan] {status_str}\n"
                    f"[bold cyan]Error:[/bold cyan] {result.error}\n"
                    f"[bold cyan]Exit Code:[/bold cyan] {result.exit_code}\n\n"
                    f"[bold cyan]Stderr (tail):[/bold cyan]\n"
                    f"{result.stderr_tail}"
                )
                console.print(Panel(details, title="[bold red]AI Connector Test: FAILED[/bold red]", expand=False))

        return 0 if result.status == "ok" else 1


def cmd_connect_ai_request(args: argparse.Namespace) -> int:
    db.init_db(_db_path(args))

    if args.task_name == "exercise.generate":
        request = generate.ExerciseGenerateRequest(
            source_id="src_dryrun",
            source_title="Dry Run Source",
            source_refs=[{
                "source_id": "src_dryrun",
                "span": {
                    "start_line": 1,
                    "end_line": 10,
                    "anchor_text": "mock"
                }
            }],
            topic="dryrun.topic",
            mission="Mock mission instructions for dry run",
        ).to_task_request()
    else:
        request = {
            "task": args.task_name,
            "version": 1,
            "instructions": f"Mock instructions for {args.task_name}",
            "payload": {"mock": True}
        }

    if args.dry_run:
        prompt = connectors.render_task_request_prompt(request)
        if _use_json(args):
            _print_json({
                "task_request": request,
                "rendered_prompt": prompt
            })
        else:
            req_panel = Panel(
                json.dumps(request, indent=2, sort_keys=True),
                title="[bold green]TaskRequest JSON[/bold green]",
                expand=False
            )
            prompt_panel = Panel(
                prompt,
                title="[bold green]Rendered Prompt[/bold green]",
                expand=False
            )
            console.print(req_panel)
            console.print(prompt_panel)
        return 0

    with db.connect(_db_path(args)) as session:
        default_conn = connectors._default_connector(session)
        if not default_conn:
            raise SystemExit("no default AI connector configured to run requests")
        connector_name = default_conn["name"]

    result = connectors.invoke_command_connector(_db_path(args), request, connector_name=connector_name)

    if _use_json(args):
        _print_json(result.to_dict())
    else:
        if result.status == "ok":
            console.print(f"[bold green]Connector invocation succeeded![/bold green] (duration: {result.duration_seconds:.2f}s)")
            console.print(Panel(result.raw_stdout, title="Stdout", expand=False))
        else:
            console.print(f"[bold red]Connector invocation failed:[/bold red] {result.error}")
            if result.stderr_tail:
                console.print(Panel(result.stderr_tail, title="Stderr (tail)", expand=False))

    return 0 if result.status == "ok" else 1


def cmd_start(args: argparse.Namespace) -> int:
    api = DojoAPI(_db_path(args))
    limit = args.limit if args.limit is not None else 5
    try:
        res = api.start_practice_session(topic=args.topic, limit=limit, reset=args.reset)
    except ValueError as exc:
        raise SystemExit(str(exc))

    is_new = res["is_new"]
    ps = res["session"]

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
        # Map to original message if active is None
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
                a["exercise_id"],
                prompt_short,
                f"{a['score'] * 100:.0f}%",
                f"{a['latency_seconds']:.1f}s",
            )
        console.print(table)
    return 0


def _is_owned_by_dojo(target_path: Path) -> bool:
    # Check SKILL.md Frontmatter signature
    skill_md = target_path / "SKILL.md"
    if skill_md.exists() and skill_md.is_file():
        try:
            content = skill_md.read_text()
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
    import shutil
    import shlex

    agent = args.agent
    dest = getattr(args, "dest", None)
    argv = None

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

    # Check ownership safety before overwriting
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

    # Auto-configure the default AI connector in the SQLite database!
    db.init_db(_db_path(args))
    with db.connect(_db_path(args)) as session:
        executable = shutil.which(agent)
        if not executable:
            # Fallback path checks
            if agent == "hermes":
                fallback = Path.home() / ".local" / "bin" / "hermes"
                if fallback.exists():
                    executable = str(fallback.resolve())
            elif agent == "openclaw":
                fallback = Path.home() / ".local" / "bin" / "openclaw"
                if fallback.exists():
                    executable = str(fallback.resolve())

        # If still not resolved, default to agent name
        if not executable:
            executable = agent

        if getattr(args, "argv", None):
            argv = shlex.split(args.argv)
        else:
            if not _use_json(args) and not getattr(args, "no_input", False) and sys.stdout.isatty():
                if agent not in ("hermes", "openclaw"):
                    try:
                        cmd_input = input(f"Enter AI connector invocation command [default: {executable}]: ").strip()
                        if cmd_input:
                            argv = shlex.split(cmd_input)
                    except (KeyboardInterrupt, EOFError):
                        pass

            if not argv:
                if agent == "hermes":
                    wrapper_path = target_path / "hermes_wrapper.sh"
                    try:
                        wrapper_content = f"#!/bin/bash\nPROMPT=$(cat)\n{executable} chat -Q -q \"$PROMPT\"\n"
                        wrapper_path.write_text(wrapper_content)
                        wrapper_path.chmod(0o755)
                        argv = [str(wrapper_path.resolve())]
                    except Exception:
                        argv = [executable, "chat", "-Q"]
                elif agent == "openclaw":
                    argv = [executable, "chat", "--stdin"]
                else:
                    argv = [executable]

        try:
            db.save_ai_connector(
                session,
                name=agent,
                argv=argv,
                is_default=True,
                replace=True,
            )
        except Exception as exc:
            raise SystemExit(f"error: failed to auto-configure AI connector for {agent}: {exc}")

    output = {
        "ok": True,
        "type": "skill_installed",
        "data": {
            "agent": agent,
            "path": str(target_path.resolve()),
            "connector": {
                "name": agent,
                "argv": argv,
                "is_default": True
            }
        }
    }

    if _use_json(args):
        _print_json(output)
    else:
        console.print(f"[bold green]Successfully installed dojo skill for {agent}![/bold green]")
        console.print(f"  Destination: [cyan]{target_path}[/cyan]")
        console.print(f"  AI Connector: Automatically registered [cyan]{agent}[/cyan] as the default connector.")
        console.print(f"               Command: [italic]{' '.join(argv)}[/italic]")

    return 0


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
            f"[bold cyan]Reason:[/bold cyan] {res['skip_reason']}\n"
        )
        if res['feedback']:
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
        res = api.correct_last_attempt(score=args.score, feedback=args.feedback, session_id=args.session)
    except ValueError as exc:
        raise SystemExit(str(exc))

    if _use_json(args):
        _print_json(res)
    else:
        feedback_text = (
            f"[bold cyan]Corrected Attempt ID:[/bold cyan] {res['id']}\n"
            f"[bold cyan]Exercise ID:[/bold cyan] {res['exercise_id']}\n"
            f"[bold cyan]New Score:[/bold cyan] [bold green]{res['score']}[/bold green] (Override)\n"
        )
        if res['feedback']:
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
                            table.add_row(h["key"], h["description"], h["status"])
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
                        table.add_row(h["key"], h["description"], h["status"])
                    console.print(table)
                else:
                    console.print(f"No active learner hypotheses/misconceptions identified for Campaign {campaign_id}.")
    return 0


def cmd_admin_debug_run(args: argparse.Namespace) -> int:
    api = DojoAPI(_db_path(args))
    res = api.get_generation_run(args.run_id)
    if res is None:
        raise SystemExit(f"error: generation run {args.run_id} not found")

    if _use_json(args):
        _print_json({
            "ok": True,
            "type": "generation_run",
            "data": res
        })
    else:
        console.print(f"\n[bold green]Generation Run Debugger - Run ID: {res['id']}[/bold green]")
        console.print(f"  [bold]Task:[/bold] [cyan]{res['task']}[/cyan]")
        console.print(f"  [bold]Status:[/bold] {'[green]ok[/green]' if res['status'] == 'ok' else '[red]failed[/red]'}")
        console.print(f"  [bold]Created At:[/bold] [cyan]{res['created_at']}[/cyan]\n")

        # 1. Request Panel
        req_str = json.dumps(res["request"], indent=2)
        console.print(Panel(req_str, title="[bold]Request JSON (Input payload)[/bold]", expand=False))

        # 2. Raw Output Panel
        console.print(Panel(res["raw_output"] or "(empty)", title="[bold]Raw AI Output (Stdout)[/bold]", expand=False))

        # 3. Diagnostics & Stderr Panel
        diag = res["diagnostics"]
        diag_str = ""
        if diag.get("diagnostics"):
            diag_str += f"[bold red]Diagnostics:[/bold red] {json.dumps(diag['diagnostics'], indent=2)}\n\n"
        if diag.get("stderr"):
            diag_str += f"[bold yellow]Stderr Tail:[/bold yellow]\n{diag['stderr']}"

        if diag_str:
            console.print(Panel(diag_str, title="[bold red]Execution Errors & Stderr[/bold red]", expand=False))
        else:
            console.print("[green]No execution diagnostics or stderr reported.[/green]")

    return 0


def cmd_feedback(args: argparse.Namespace) -> int:
    api = DojoAPI(_db_path(args))
    try:
        res = api.add_learner_feedback(
            content=args.comment,
            campaign_id=args.campaign,
            attempt_id=args.attempt,
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
            f"[bold cyan]Topic Path:[/bold cyan] {res['topic_path'] or 'None'}\n"
        )
        if res.get('attempt_id'):
            feedback_text += f"[bold cyan]Attempt ID:[/bold cyan] {res['attempt_id']}\n"
        feedback_text += f"[bold cyan]Content:[/bold cyan] {res['description']}\n"
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


def cmd_campaign_create(args: argparse.Namespace) -> int:
    api = DojoAPI(_db_path(args))

    # 1. Print campaign initialization. Call api.create_campaign(...)
    if not _use_json(args):
        console.print("[bold green]Initializing learning campaign...[/bold green]")

    try:
        res = api.create_campaign(
            goal=args.goal,
            level=args.level,
            name=args.name,
            exclusions=args.exclude,
            feedback=args.feedback,
        )
    except Exception as exc:
        raise SystemExit(f"error: campaign creation failed: {exc}")

    campaign_id = res["campaign_id"]
    session_id = None
    exercise_ids = []

    try:
        # 2. If a source file/URL was passed, ingest it and call api.attach_source_to_campaign(...)
        if hasattr(args, "source") and args.source:
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
                    content = file_path.read_text()
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
            api.attach_source_to_campaign(campaign_id, source_res["source_id"])

        # 3. Trigger diagnostic generation via api.start_practice_session(...)
        if not _use_json(args):
            sess_res = api.start_practice_session(campaign_id=campaign_id)
            session = sess_res["session"]
            session_id = session["id"]
            exercise_ids = session["exercise_ids"]

            # Fetch campaign details after JIT update
            with db.connect(api.db_path) as db_sess:
                campaign = db_sess.get(db.Campaign, campaign_id)
                campaign_name = campaign.name
                campaign_topic = campaign.topic_path

            # 4. Render detected topic and title in a beautiful Panel
            header_text = (
                f"[bold green]Campaign Name:[/bold green] [yellow]{campaign_name}[/yellow]\n"
                f"[bold green]Campaign ID:[/bold green] [cyan]{campaign_id}[/cyan]\n"
                f"[bold green]Topic Path Namespace:[/bold green] [cyan]{campaign_topic}[/cyan]"
            )
            console.print(Panel(header_text, title="🚀 [bold green]Campaign Onboarding Diagnostic[/bold green]", expand=False, border_style="green"))

            # 5. Present onboarding questions using a styled interactive loop, collecting answers via api.submit_answer(...)
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

            # 6. Trigger consolidation via api.consolidate_learner_profile(...)
            consolidate_res = api.consolidate_learner_profile(campaign_id=campaign_id)

            # Fetch updated campaign details after consolidation
            with db.connect(api.db_path) as db_sess:
                campaign = db_sess.get(db.Campaign, campaign_id)
                camp_data = db._campaign_from_model(campaign)

            # 7. Render finalized syllabus and attack plan
            if camp_data.get("syllabus_markdown"):
                from rich.markdown import Markdown
                console.print()
                console.print(Panel(
                    Markdown(camp_data["syllabus_markdown"]),
                    title="📚 [bold green]Campaign Syllabus[/bold green]",
                    border_style="green"
                ))

            if camp_data.get("attack_plan"):
                from rich.tree import Tree
                tree = Tree("[bold cyan]Curriculum Attack Plan Timeline[/bold cyan]")
                for p in camp_data["attack_plan"]:
                    phase_idx = p["phase"]
                    topics_str = ", ".join(p.get("topics") or [])
                    crit = p.get("criteria") or {}
                    criteria_str = f"min_attempts={crit.get('min_attempts', 0)}, min_accuracy={crit.get('min_accuracy', 0.0)}"

                    if phase_idx == camp_data["active_phase_index"]:
                        phase_node = tree.add(f"[bold yellow]▶ Phase {phase_idx} (Active)[/bold yellow]")
                        phase_node.add(f"[bold yellow]Topics:[/bold yellow] [yellow]{topics_str}[/yellow]")
                        phase_node.add(f"[bold yellow]Target Criteria:[/bold yellow] [dim]{criteria_str}[/dim]")
                    else:
                        status_style = "dim" if phase_idx < camp_data["active_phase_index"] else "cyan"
                        phase_node = tree.add(f"[{status_style}]Phase {phase_idx}[/{status_style}]")
                        phase_node.add(f"[bold {status_style}]Topics:[/bold {status_style}] {topics_str}")
                        phase_node.add(f"[bold {status_style}]Target Criteria:[/bold {status_style}] [dim]{criteria_str}[/dim]")
                console.print()
                console.print(tree)

            console.print("\n[bold green]Campaign setup and diagnostic calibration complete![/bold green]")
            console.print("To begin practicing, run: [bold cyan]dojo start[/bold cyan]\n")

        else:
            # In JSON mode, we just return the campaign creation metadata directly
            _print_json({
                "ok": True,
                "type": "campaign_created",
                "data": res
            })

    except (KeyboardInterrupt, Exception) as exc:
        if not _use_json(args):
            console.print()
            if isinstance(exc, KeyboardInterrupt):
                console.print("[bold red]Campaign creation cancelled. Cleaning up database...[/bold red]")
            else:
                console.print(f"[bold red]Campaign creation failed ({exc}). Cleaning up database...[/bold red]")

        try:
            from sqlmodel import text
            with db.connect(api.db_path) as db_sess:
                # Delete attempts associated with this campaign or session
                db_sess.execute(text("DELETE FROM attempts WHERE campaign_id = :cid"), {"cid": campaign_id})
                if session_id:
                    db_sess.execute(text("DELETE FROM attempts WHERE session_id = :sid"), {"sid": session_id})
                    db_sess.execute(text("DELETE FROM practice_sessions WHERE id = :sid"), {"sid": session_id})

                # Delete JIT diagnostic exercises
                if exercise_ids:
                    for ex_id in exercise_ids:
                        db_sess.execute(text("DELETE FROM exercises WHERE id = :eid"), {"eid": ex_id})

                # Delete the campaign
                db_sess.execute(text("DELETE FROM campaigns WHERE id = :cid"), {"cid": campaign_id})
                db_sess.commit()
        except Exception as cleanup_exc:
            api.log.error(f"Failed to clean up campaign '{campaign_id}': {cleanup_exc}")

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
            with db.connect(api.db_path) as session:
                camp = session.get(db.Campaign, args.campaign_id)
                camp_data = db._campaign_from_model(camp)

            if camp_data.get("sources_config"):
                table = Table(title="Linked Campaign Sources")
                table.add_column("Source ID", style="cyan")
                table.add_column("Purpose", style="green")
                table.add_column("Mapped Topics", style="magenta")
                for link in camp_data["sources_config"]:
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
        console.print(f"\n[bold green]Pedagogical Journal for Campaign: {res['name']}[/bold green]")
        console.print(f"  Campaign ID: [cyan]{res['campaign_id']}[/cyan]")
        console.print(f"  Active Phase Index: [cyan]{res['active_phase_index']}[/cyan]\n")

        if not res["journal"]:
            console.print("No journal entries logged yet.")
            return 0

        for i, entry in enumerate(res["journal"], 1):
            timestamp_short = entry["timestamp"].split("T")[0]
            console.print(
                f"[bold cyan][{i}] {timestamp_short} - Action: {entry['action']}[/bold cyan] "
                f"(Phase: {entry['active_phase_index']}, Status: {entry.get('status', 'resolved')})"
            )
            console.print(f"    [bold]Trigger:[/bold] {entry['trigger']}")
            console.print(f"    [bold]Hypothesis:[/bold] {entry['hypothesis']}")

            perf = entry.get("performance_snapshot")
            if perf:
                console.print(f"    [bold]Performance at time:[/bold] attempts={perf.get('attempts', 0)}, accuracy={perf.get('accuracy', 0.0)*100:.1f}%, latency={perf.get('average_latency_seconds', 0.0):.1f}s")

            if getattr(args, "show_snapshots", False):
                from rich.markup import escape
                console.print(f"    [bold]Plan Snapshot:[/bold]")
                plan = entry.get("plan_snapshot") or []
                for p in plan:
                    topics_str = ", ".join(p.get("topics") or [])
                    criteria_str = ", ".join(f"{k}={v}" for k, v in p.get("criteria", {}).items())
                    console.print(f"      - Phase {p.get('phase', '?')}: topics=\\[{escape(topics_str)}], criteria=\\[{escape(criteria_str)}]")
            console.print()
    return 0


def cmd_campaign_export(args: argparse.Namespace) -> int:
    api = DojoAPI(_db_path(args))
    campaign_id = args.campaign

    if campaign_id == "latest":
        try:
            history = api.get_campaign_history(None)
            campaign_id = history["campaign_id"]
        except Exception as exc:
            raise SystemExit(f"error: failed to resolve latest campaign: {exc}")

    output_path = args.output
    if not output_path:
        try:
            with db.connect(api.db_path) as session:
                camp = session.get(db.Campaign, campaign_id)
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
            format_type=args.format
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
        console.print(f"  Campaign: [cyan]{res['name']}[/cyan]")
        console.print(f"  Format: [cyan]{res['format'].upper()}[/cyan]")
        console.print(f"  Output Path: [cyan]{res['output_path']}[/cyan]")
    return 0


def build_parser() -> argparse.ArgumentParser:

    parser = argparse.ArgumentParser(prog="dojo")
    parser.add_argument("--db", help="SQLite database path")
    parser.add_argument("--json", action="store_true", help="output structured JSON instead of human-friendly text")
    parser.add_argument("--no-input", action="store_true", help="disable all interactive prompts")
    sub = parser.add_subparsers(dest="command", required=True)

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
    p_correct.add_argument("--session")
    p_correct.add_argument("--score", type=float, default=1.0)
    p_correct.set_defaults(func=cmd_correct)

    p_feedback = sub.add_parser("feedback")
    p_feedback.add_argument("comment")
    p_feedback.add_argument("--campaign")
    p_feedback.add_argument("--attempt")
    p_feedback.set_defaults(func=cmd_feedback)

    p_admin = sub.add_parser("admin")
    p_admin_sub = p_admin.add_subparsers(dest="admin_command", required=True)
    p_consolidate = p_admin_sub.add_parser("consolidate")
    p_consolidate.add_argument("--campaign")
    p_consolidate.set_defaults(func=cmd_admin_consolidate)

    p_debug_run = p_admin_sub.add_parser("debug-run")
    p_debug_run.add_argument("run_id", type=int, help="Generation run ID to inspect")
    p_debug_run.set_defaults(func=cmd_admin_debug_run)

    p_config = sub.add_parser("config")
    p_config_sub = p_config.add_subparsers(dest="config_command", required=True)
    p_config_set = p_config_sub.add_parser("set")
    p_config_set.add_argument("key")
    p_config_set.add_argument("value")
    p_config_set.set_defaults(func=cmd_config_set)
    p_config_show = p_config_sub.add_parser("show")
    p_config_show.set_defaults(func=cmd_config_show)

    connect = sub.add_parser("connect")
    connect_sub = connect.add_subparsers(dest="connect_command", required=True)
    ai = connect_sub.add_parser("ai")
    ai_sub = ai.add_subparsers(dest="ai_command", required=True)

    p_command = ai_sub.add_parser("command")
    p_command.add_argument("name")
    p_command.add_argument("--default", action="store_true")
    p_command.add_argument("--input", default="stdin-prompt", choices=["stdin-prompt", "stdin-json", "request-json-file"])
    p_command.add_argument("--output", default="stdout-json-or-text", choices=["stdout-json-or-text"])
    p_command.add_argument("--timeout", type=int, default=120)
    p_command.add_argument("--replace", action="store_true")
    p_command.add_argument("command", nargs=argparse.REMAINDER)
    p_command.set_defaults(func=cmd_connect_ai_command)

    p_list = ai_sub.add_parser("list")
    p_list.set_defaults(func=cmd_connect_ai_list)
    p_show = ai_sub.add_parser("show")
    p_show.add_argument("name")
    p_show.set_defaults(func=cmd_connect_ai_show)
    p_use = ai_sub.add_parser("use")
    p_use.add_argument("name")
    p_use.set_defaults(func=cmd_connect_ai_use)
    p_default = ai_sub.add_parser("default", help="deprecated alias for use")
    p_default.add_argument("name")
    p_default.set_defaults(func=cmd_connect_ai_use)
    p_remove = ai_sub.add_parser("remove")
    p_remove.add_argument("name")
    p_remove.add_argument("--force", action="store_true")
    p_remove.set_defaults(func=cmd_connect_ai_remove)

    p_test = ai_sub.add_parser("test")
    p_test.add_argument("name", nargs="?")
    p_test.set_defaults(func=cmd_connect_ai_test)

    p_request = ai_sub.add_parser("request")
    p_request.add_argument("task_name")
    p_request.add_argument("--dry-run", action="store_true")
    p_request.set_defaults(func=cmd_connect_ai_request)

    p_campaign = sub.add_parser("campaign")
    p_camp_sub = p_campaign.add_subparsers(dest="campaign_command", required=True)

    p_camp_create = p_camp_sub.add_parser("create")
    p_camp_create.add_argument("goal", help="The user's high-level learning goal or target skill")
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
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
