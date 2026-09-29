"""CLI package entry abstraction."""
import argparse
import os
import sys
import uuid
from typing import Any, List, Optional

from clairecoder.app import ClaireCoderV1
from clairecoder.gateway.types import ModelError
from clairecoder.tui.app import TuiApplication


def run_direct(
    objective: str,
    session_id: Optional[str] = None,
    app: Optional[ClaireCoderV1] = None,
) -> int:
    """Execute direct non-interactive objective submission via ClaireCoderV1 application."""
    if app is None:
        app = ClaireCoderV1(workspace_root=os.getcwd())

    # Load persisted provider configuration
    app.load_providers_from_config()

    sid = session_id or f"cli_{uuid.uuid4().hex[:8]}"
    try:
        app.resume_session(sid)
        print(f"Resumed session: {sid}")
    except (ValueError, FileNotFoundError):
        app.create_session(sid)

    print(f"Executing objective: {objective}")
    app.submit_objective(sid, objective, start_background=False)

    try:
        app.run(sid)
        status = app.status(sid)
        obj_status = status.get("objective", {}).get("status", "unknown")
        print(f"Execution finished with status: {obj_status}")
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
    except (ValueError, FileNotFoundError):
        app.create_session(sid)

    tui = TuiApplication(workspace_root=os.getcwd())
    tui.connect_controller(app.interaction_controller)
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

    try:
        parsed_args = parser.parse_args(args)
    except SystemExit as e:
        return e.code

    if parsed_args.version:
        app = ClaireCoderV1()
        print(f"ClaireCoder {app.get_version()}")
        return 0

    if parsed_args.objective:
        return run_direct(parsed_args.objective, session_id=parsed_args.session)
    else:
        return run_interactive(session_id=parsed_args.session)
