"""Developer preview harness for visual inspection of the ClaireCoder TUI."""
import sys
from typing import List, Optional

from .app import TuiApplication
from .states import InputState, TerminalMode
from .terminal import TerminalCapability
from .activity import ActivityModel, ActivityType, ActivityState, DiffInfo, DiffLine
from .diff import FileDiff, DiffRenderer
from .loading import LoadingScreen
from .task import WorkflowTaskItem

def create_preview_app(mode: Optional[TerminalMode] = None) -> TuiApplication:
    """Creates a pre-populated TuiApplication with realistic mock session state matching reference."""
    term = TerminalCapability(width=104, height=30, mode=mode)
    app = TuiApplication(terminal=term)
    app.transcript.resize(20)

    # 1. Populate Header
    app.header.directory = "~/projects/claire-speech-engine"
    app.header.model = "claire-large"
    app.header.mode = "IMPLEMENT"
    app.header.session_id = "main"
    app.header.task_progress = "2/5"
    app.header.context_usage = "12.4k/200k"

    # Populate Task View for preview
    app.task_view.tasks = [
        WorkflowTaskItem(1, "Understand objective", "✓"),
        WorkflowTaskItem(2, "Plan changes", "✓"),
        WorkflowTaskItem(3, "Implement changes", "▶"),
        WorkflowTaskItem(4, "Verify", "○"),
        WorkflowTaskItem(5, "Complete", "○"),
    ]
    app.task_view.progress_pct = 40
    app.task_view.objective = "Add streaming decode support with fallback to greedy decoding"

    # 2. Populate Transcript
    # Activity 1: Reading
    app.transcript.append_activity(ActivityModel(
        type=ActivityType.READING,
        state=ActivityState.COMPLETED,
        title="Reading src/decoder.py"
    ))

    # Activity 2: Editing with Diff
    diff = DiffInfo(
        summary="+18 -4",
        lines=[
            DiffLine(type="context", content="def decode(self, tokens):"),
            DiffLine(type="remove", content="    return self._greedy(tokens)"),
            DiffLine(type="add", content="    if self.streaming:"),
            DiffLine(type="add", content="        return self._stream_decode(tokens)"),
            DiffLine(type="add", content="    return self._greedy(tokens)"),
            DiffLine(type="context", content="..."),
        ]
    )
    boxed_diff_lines = DiffRenderer.render_inline_diff(diff, file_path="", mode=mode, width=54, expanded=True)
    boxed_diff_text = "\n".join(boxed_diff_lines) + "\n+18 -4"
    edit_act = ActivityModel(
        type=ActivityType.EDITING,
        state=ActivityState.COMPLETED,
        title="Editing src/decoder.py",
        expandable_content=boxed_diff_text,
        expanded=True
    )
    app.transcript.append_activity(edit_act)

    # Activity 3: Pytest
    app.transcript.append_activity(ActivityModel(
        type=ActivityType.TEST,
        state=ActivityState.COMPLETED,
        title="Running pytest tests/decoder/",
        detail="12 passed in 1.2s"
    ))

    # Activity 4: Verification
    app.transcript.append_activity(ActivityModel(
        type=ActivityType.VERIFICATION,
        state=ActivityState.COMPLETED,
        title="Verification passed",
        detail="All criteria satisfied."
    ))

    # Activity 5: Assistant message (Claire textual persona)
    app.transcript.append_activity(ActivityModel(
        type=ActivityType.MESSAGE,
        state=ActivityState.COMPLETED,
        title="Claire",
        detail="Streaming decode support added with a safe fallback.\nAll tests are passing.\nWhat would you like to work on next?"
    ))

    # 3. Populate Review Overlay with sample changed files
    sample_files = [
        FileDiff(
            file_path="src/decoder.py",
            additions=18,
            deletions=4,
            lines=[
                DiffLine(type="context", content="def decode(self, tokens):"),
                DiffLine(type="remove", content="    return self._greedy(tokens)"),
                DiffLine(type="add", content="    if self.streaming:"),
                DiffLine(type="add", content="        return self._stream_decode(tokens)"),
                DiffLine(type="add", content="    return self._greedy(tokens)"),
            ]
        ),
        FileDiff(
            file_path="src/router.py",
            additions=6,
            deletions=0,
            is_new=True,
            lines=[
                DiffLine(type="add", content="class StreamingRouter:"),
                DiffLine(type="add", content="    def route_audio(self, stream):"),
                DiffLine(type="add", content="        pass"),
            ]
        ),
        FileDiff(
            file_path="tests/test_decoder.py",
            additions=22,
            deletions=0,
            lines=[
                DiffLine(type="add", content="def test_streaming_decode():"),
                DiffLine(type="add", content="    decoder = Decoder(streaming=True)"),
                DiffLine(type="add", content="    assert decoder.decode([1, 2]) is not None"),
            ]
        ),
    ]
    app.review_overlay.set_files(sample_files)

    # 4. Set prompt
    app.prompt.set_text("add support for interrupting mid-stream")
    return app


def render_preview(screen: str = "main", mode: Optional[TerminalMode] = None,
                   use_color: bool = True) -> List[str]:
    """Renders a specific screen view of the TUI preview harness."""
    if screen == "loading":
        return LoadingScreen.render(width=56, height=38, use_color=use_color)

    app = create_preview_app(mode=mode)

    if screen == "permission":
        app.permission_surface.request_confirmation(
            request_id="prev_req_1",
            tool_id="rm",
            action="delete",
            resource="src/decoder_v1_deprecated.py",
            reason="This will permanently delete the file."
        )
        app.set_state(InputState.CONFIRMATION)
    elif screen == "review":
        app.open_review()
    elif screen == "palette":
        app.open_palette()
    elif screen in ("tree", "file_tree"):
        app.open_tree()
    elif screen in ("task", "workflow"):
        app.open_task()
    else:
        app.set_state(InputState.NORMAL)

    return app.render()


def main() -> None:
    """Entry point for CLI manual inspection."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    screen = "main"
    if len(sys.argv) > 1:
        screen = sys.argv[1].lower()

    lines = render_preview(screen=screen)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
