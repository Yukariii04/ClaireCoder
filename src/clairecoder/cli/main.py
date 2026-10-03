"""CLI package entry abstraction."""
import argparse
import os
import sys
import uuid
from typing import Any, List, Optional

from clairecoder.app import ClaireCoderV1
from clairecoder.engine.types import EngineEvent
from clairecoder.gateway.types import ModelError
from clairecoder.tui.app import TuiApplication
from clairecoder.session.store import SessionStore
from clairecoder.session.errors import SessionNotFoundError, SessionError


def run_direct(
    objective: str,
    session_id: Optional[str] = None,
    app: Optional[ClaireCoderV1] = None,
) -> int:
    """Execute an objective, prompting for supervised tool approvals when interactive."""
    if app is None:
        app = ClaireCoderV1(workspace_root=os.getcwd())

    # Load persisted provider configuration
    app.load_providers_from_config()

    sid = session_id or f"cli_{uuid.uuid4().hex[:8]}"
    try:
        app.resume_session(sid)
        print(f"Resumed session: {sid}")
    except (ValueError, FileNotFoundError, SessionError, KeyError):
        app.create_session(sid)

    print(f"Executing objective: {objective}")
    app.submit_objective(sid, objective, start_background=False)

    try:
        if sys.stdin.isatty():
            def request_permission(event, payload):
                if event != EngineEvent.PERMISSION_REQUESTED:
                    return
                command = payload.get("command") or f"{payload.get('action', 'use')} {payload.get('resource', '')}".strip()
                print(f"\nPermission requested: {command}")
                while True:
                    answer = input("Allow once [y], allow for this session [a], or deny [n]? ").strip().lower()
                    if answer in {"y", "yes"}:
                        decision = "approve"
                        break
                    if answer in {"a", "always", "always_session"}:
                        decision = "always_session"
                        break
                    if answer in {"n", "no", "deny"}:
                        decision = "deny"
                        break
                    print("Enter y, a, or n.")

                app.interaction_controller.handle_permission_response(
                    request_id=payload.get("request_id", ""),
                    decision=decision,
                    session_id=payload.get("session_id"),
                    tool_id=payload.get("tool_id") or payload.get("tool_name"),
                    action=payload.get("action"),
                    resource=payload.get("resource"),
                    command=payload.get("command"),
                    category=payload.get("category"),
                )

            app.engineering_engine.subscribe(request_permission)
        else:
            # A headless invocation cannot resolve supervised tool requests.
            # Fail promptly with guidance instead of waiting for a UI that is absent.
            app.engineering_engine.permission_wait_timeout_seconds = 0.0

        result = app.run(sid)
        status = app.status(sid)
        obj_status = status.get("objective", {}).get("status", "unknown")
        print(f"Execution finished with status: {obj_status}")
        if not result.success and result.failure_reason:
            print(f"Execution failed: {result.failure_reason}", file=sys.stderr)
        return 0 if obj_status == "completed" else 1
    except ModelError as me:
        print(f"Model error: {me}", file=sys.stderr)
        print(
            "Stage 7 provider configuration is required for live external model execution.",
            file=sys.stderr,
        )
        print(
            "Run 'clairecoder' interactively to configure a model provider.",
            file=sys.stderr,
        )
        return 1
    except KeyboardInterrupt:
        print("Operation interrupted by user (Ctrl+C).", file=sys.stderr)
        try:
            app.engineering_engine.interrupt_execution(sid)
        except Exception:
            pass
        return 130
    except Exception as e:
        print(f"Application error: {e}", file=sys.stderr)
        return 1


def run_interactive(
    session_id: Optional[str] = None,
    app: Optional[ClaireCoderV1] = None,
    input_source: Optional[Any] = None,
) -> int:
    """Launch persistent interactive TUI session delegated to TuiApplication."""
    if app is None:
        app = ClaireCoderV1(workspace_root=os.getcwd())

    # Load persisted provider configuration into ModelGateway
    app.load_providers_from_config()

    sid = session_id or f"cli_{uuid.uuid4().hex[:8]}"
    try:
        app.resume_session(sid)
    except (ValueError, FileNotFoundError, SessionError, KeyError):
        app.create_session(sid)

    tui = TuiApplication(workspace_root=os.getcwd())
    tui.connect_controller(app.interaction_controller)
    tui.connect_runtime(app.event_emitter)
    tui.connect_config_manager(app.config_manager)
    tui.register_runtime_sync_callback(app.load_providers_from_config)

    # Set active session on the controller
    app.interaction_controller._active_session_id = sid
    tui.header.session_id = sid

    # Synchronize header with active model info from config
    active = app.config_manager.get_active()
    if active.get("model_id"):
        tui.header.model = active["model_id"]
        # Update context capacity from the registered model
        registered = getattr(app.model_gateway, "_models", {})
        model_obj = registered.get(active["model_id"])
        if model_obj and hasattr(model_obj, "context_capacity") and model_obj.context_capacity:
            app.interaction_controller._context_capacity = model_obj.context_capacity

    # Synchronize mode from the controller
    tui.header.mode = app.interaction_controller.mode.value.upper()

    return tui.run(input_source=input_source)


def run_cli(args: Optional[List[str]] = None) -> int:
    """
    CLI package/module entry abstraction.
    Establishes the boundary for interactive TUI vs non-interactive CLI.
    """
    if args is None:
        args = sys.argv[1:]

    parser = argparse.ArgumentParser(
        prog="clairecoder", description="ClaireCoder V1 Developer CLI"
    )

    parser.add_argument(
        "objective",
        nargs="?",
        help="Direct engineering objective for non-interactive execution",
    )
    parser.add_argument(
        "--version", action="store_true", help="Print version information"
    )
    parser.add_argument(
        "--session", type=str, help="Optional session ID to resume or create"
    )
    parser.add_argument(
        "--resume", type=str, metavar="SESSION_ID", help="Resume an existing session by ID"
    )
    parser.add_argument(
        "--list-sessions", action="store_true", help="List persisted sessions"
    )
    parser.add_argument(
        "--inspect-session", type=str, metavar="SESSION_ID", help="Inspect a persisted session by ID"
    )

    try:
        parsed_args = parser.parse_args(args)
    except SystemExit as e:
        return e.code

    if parsed_args.version:
        app = ClaireCoderV1()
        print(f"ClaireCoder {app.get_version()}")
        return 0

    if parsed_args.list_sessions:
        store = SessionStore(workspace_root=os.getcwd())
        sessions = store.list()
        if not sessions:
            print("No sessions found.")
            return 0
        print(f"{'SESSION ID':<20} {'STATUS':<12} {'UPDATED AT':<26} {'OBJECTIVE'}")
        print("-" * 78)
        for s in sessions:
            obj_summary = (s.original_objective[:30] + "...") if len(s.original_objective) > 30 else s.original_objective
            print(f"{s.session_id:<20} {s.status.value:<12} {s.updated_at:<26} {obj_summary}")
        return 0

    if parsed_args.inspect_session:
        store = SessionStore(workspace_root=os.getcwd())
        try:
            sess = store.get(parsed_args.inspect_session)
            print(f"Session ID:         {sess.session_id}")
            print(f"Status:             {sess.status.value}")
            print(f"Created At:         {sess.created_at}")
            print(f"Updated At:         {sess.updated_at}")
            print(f"Workspace Root:     {sess.workspace_root}")
            print(f"Objective:          {sess.original_objective}")
            print(f"Turn Count:         {sess.turn_count}")
            print(f"Current Task:       {sess.current_task_id or 'None'}")
            tasks_cnt = len(sess.task_graph_state.get('tasks', [])) if sess.task_graph_state else 0
            print(f"Tasks Total:        {tasks_cnt}")
            print(f"ChangeSets:         {len(sess.changesets)}")
            return 0
        except SessionNotFoundError:
            print(f"Error: Session '{parsed_args.inspect_session}' not found.", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error inspecting session: {e}", file=sys.stderr)
            return 1

    target_session = parsed_args.resume or parsed_args.session
    if parsed_args.objective:
        return run_direct(parsed_args.objective, session_id=target_session)
    else:
        return run_interactive(session_id=target_session)
