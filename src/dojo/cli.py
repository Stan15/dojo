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
            kind = "url"
            path_str = args.path
            title = args.title or args.path
            content = f"Content of URL: {args.path}"
        else:
            kind = "file"
            file_path = Path(args.path)
            if not file_path.exists():
                raise SystemExit(f"file not found: {args.path}")
            content = file_path.read_text()
            title = args.title or file_path.name
            path_str = str(file_path.resolve())
    else:
        kind = "text"
        content = args.text
        title = args.title

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
    source = api.get_source(args.name)
    if source is None:
        raise SystemExit(f"unknown source: {args.name}")
    if _use_json(args):
        _print_json(source)
    else:
        details = (
            f"[bold cyan]ID:[/bold cyan] {source['id']}\n"
            f"[bold cyan]Kind:[/bold cyan] {source['kind']}\n"
            f"[bold cyan]Path:[/bold cyan] {source['path'] or 'N/A'}\n"
            f"[bold cyan]Mission:[/bold cyan] {source['mission'] or 'None'}\n"
            f"[bold cyan]Candidates Left:[/bold cyan] {source['candidates_count']}\n"
            f"[bold cyan]Created At:[/bold cyan] {source['created_at']}\n\n"
            f"[bold cyan]Content Excerpt:[/bold cyan]\n"
            f"{source['content'][:300] + '...' if len(source['content']) > 300 else source['content']}"
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
            f"[bold cyan]Session ID:[/bold cyan] {output_data['session_id']}\n"
            f"[bold cyan]Exercise {output_data['index'] + 1}/{output_data['total']}:[/bold cyan] {output_data['exercise_id']}\n"
            f"[bold cyan]Topic Path:[/bold cyan] {output_data['topic_path']}\n"
            f"[bold cyan]Difficulty:[/bold cyan] {output_data['difficulty'] or 'N/A'}\n\n"
            f"[bold green]Prompt:[/bold green]\n"
            f"{output_data['prompt']}"
        )
        console.print(Panel(card_text, title="Practice Prompt", expand=False))
        console.print("  Type your answer and run: [bold]dojo answer \"your response\"[/bold]")
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
            result_str = "[bold green]CORRECT[/bold green]"
        else:
            result_str = "[bold red]INCORRECT[/bold red]"
            
        feedback = (
            f"[bold cyan]Attempt ID:[/bold cyan] {output_data['attempt_id']}\n"
            f"[bold cyan]Result:[/bold cyan] {result_str}\n"
            f"[bold cyan]Your Answer:[/bold cyan] {output_data['user_answer']}\n"
            f"[bold cyan]Correct Answer:[/bold cyan] {output_data['correct_answer'] or 'N/A (Rubric-graded)'}\n"
            f"[bold cyan]Latency:[/bold cyan] {output_data['latency_seconds']:.2f} seconds\n\n"
        )
        if output_data["is_session_completed"]:
            feedback += "[bold green]Practice session completed![/bold green] Run 'dojo progress' to check your metrics."
        else:
            feedback += f"Run [bold]dojo ready[/bold] for the next exercise ({output_data['next_index'] + 1}/{output_data['total_exercises']})."
            
        console.print(Panel(feedback, title="Practice Results", expand=False))
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
            f"[bold cyan]Total Practice Attempts:[/bold cyan] {total}\n"
            f"[bold cyan]Average Accuracy:[/bold cyan] {avg_score * 100:.1f}%\n"
            f"[bold cyan]Average Recall Latency:[/bold cyan] {avg_latency:.2f} seconds\n"
        )
        console.print(Panel(stats, title="Dojo Practice Progress Summary", expand=False))
        
        table = Table(title="Recent Practice Attempts (Last 10)")
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


def cmd_install(args: argparse.Namespace) -> int:
    import shutil
    
    agent = args.agent
    if not agent:
        if _use_json(args) or getattr(args, "no_input", False) or not sys.stdout.isatty():
            raise SystemExit("must specify agent name (choices: hermes, openclaw) in non-interactive mode")
        
        console.print("[bold cyan]Please select the target agent to install the Dojo skill into:[/bold cyan]")
        console.print("  [1] [bold]Hermes[/bold] (~/.hermes/skills/dojo)")
        console.print("  [2] [bold]OpenClaw[/bold] (~/.openclaw/skills/dojo)")
        console.print("  [q] Quit")
        
        try:
            choice = input("\nSelect an option [1-2, q]: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Installation cancelled.[/yellow]")
            return 1
            
        if choice == "1":
            agent = "hermes"
        elif choice == "2":
            agent = "openclaw"
        else:
            console.print("[yellow]Cancelled.[/yellow]")
            return 0

    home = Path.home()
    
    if agent == "hermes":
        target_path = home / ".hermes" / "skills" / "dojo"
    elif agent == "openclaw":
        target_path = home / ".openclaw" / "skills" / "dojo"
    else:
        raise SystemExit(f"unknown agent: {agent}")
        
    if hasattr(sys, "_MEIPASS"):
        repo_skills_dojo = Path(getattr(sys, "_MEIPASS")) / "skills" / "dojo"
    else:
        repo_skills_dojo = Path(__file__).resolve().parent.parent.parent / "skills" / "dojo"
        
    if not repo_skills_dojo.exists():
        raise SystemExit(f"error: skills/dojo directory not found at {repo_skills_dojo}")
        
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
            
        if agent == "hermes":
            argv = [executable, "chat", "-Q", "--stdin"]
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
    p_add.add_argument("--generate", action="store_true")
    p_add.set_defaults(func=cmd_add)

    p_source = sub.add_parser("source")
    p_source_sub = p_source.add_subparsers(dest="source_command", required=True)

    p_src_list = p_source_sub.add_parser("list")
    p_src_list.set_defaults(func=cmd_source_list)

    p_src_show = p_source_sub.add_parser("show")
    p_src_show.add_argument("name")
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
    p_install.add_argument("agent", nargs="?", choices=["hermes", "openclaw"])
    p_install.set_defaults(func=cmd_install)

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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
