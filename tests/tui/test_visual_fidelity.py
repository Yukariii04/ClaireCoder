"""Visual regression and compositional fidelity tests for Stage 5 Terminal Experience Finalization."""
import pytest
from clairecoder.tui.preview import render_preview, create_preview_app
from clairecoder.tui.loading import LoadingScreen
from clairecoder.tui.tree import FileTreeOverlay
from clairecoder.tui.task import TaskViewOverlay
from clairecoder.tui.canvas import Canvas, VisualNode, visible_length
from clairecoder.tui.states import InputState, TerminalMode

def test_main_tui_composition_fidelity():
    """Verify Main TUI compositional fidelity matching TUI-DESIGN.md Section 4 reference."""
    lines = render_preview("main", use_color=False)
    full_text = "\n".join(lines)

    # 1. Outer frame & Title
    assert "╭─ ClaireCoder" in lines[0]
    assert "● v0.1.0 ─╮" in lines[0]
    assert "╰" in lines[-1] and "╯" in lines[-1]

    # 2. Status Row
    assert "dir: ~/projects/claire-speech-engine" in full_text
    assert "model: claire-large" in full_text
    assert "mode: IMPLEMENT" in full_text
    assert "session: main" in full_text
    assert "task: 2/5" in full_text
    assert "context: 12.4k/200k" in full_text

    # 3. Activity Markers & Transcript
    assert "> ✓ Reading src/decoder.py" in full_text
    assert "> ● Editing src/decoder.py" in full_text
    assert "+18 -4" in full_text
    assert "> ● Running pytest tests/decoder/" in full_text
    assert "12 passed in 1.2s" in full_text
    assert "> ✓ Verification passed" in full_text
    assert "All criteria satisfied." in full_text

    # 4. Claire Text Persona Message
    assert "Claire:" in full_text
    assert "Streaming decode support added with a safe fallback." in full_text
    assert "All tests are passing." in full_text
    assert "What would you like to work on next?" in full_text

    # 5. Verify NO graphical mascot placeholders or internal mascot state names appear
    assert "[Claire IDLE]" not in full_text
    assert "[Claire WORKING]" not in full_text
    assert "[Claire THINKING]" not in full_text
    assert "mascot: IDLE" not in full_text
    assert "mascot_idle" not in full_text
    assert "▄████▄" not in full_text

    # 6. Prompt & Footer
    assert "> add support for interrupting mid-stream█" in full_text
    assert "ctrl+c interrupt" in full_text
    assert "ctrl+t file tree" in full_text
    assert "ctrl+r review changes" in full_text
    assert "ctrl+p task view" in full_text
    assert "? help" in full_text
    assert "/commands" in full_text

def test_loading_screen_composition_fidelity():
    """Verify Loading screen visual composition matching TUI-DESIGN.md Section 10 reference."""
    lines = render_preview("loading", use_color=False)
    full_text = "\n".join(lines)

    assert "CLAIRECODER" in full_text
    assert "Engineering. Automated." in full_text
    assert "Initializing ClaireCoder Engine..." in full_text
    assert "> Loading configuration" in full_text
    assert "> Connecting model gateway" in full_text
    assert "> Registering tools" in full_text
    assert "> Preparing workspace" in full_text
    assert "> Loading skills" in full_text
    assert "> Starting session" in full_text
    assert "[ OK ]" in full_text
    assert "Launching..." in full_text
    assert "100%" in full_text
    assert '"Let\'s build something amazing together."' in full_text
    assert "- Claire" in full_text

    # Verify NO graphical chibi/half-block mascot in loading screen
    assert "▄████▄" not in full_text
    assert "▀████▀" not in full_text

def test_permission_screen_composition_fidelity():
    """Verify Permission prompt visual composition matching TUI-DESIGN.md Section 8 reference."""
    lines = render_preview("permission", use_color=False)
    full_text = "\n".join(lines)

    assert "Permission Required" in full_text
    assert "ClaireCoder wants to run:" in full_text
    assert "$ rm src/decoder_v1_deprecated.py" in full_text
    assert "[y] yes" in full_text
    assert "[n] no" in full_text
    assert "[a] yes, always this sess" in full_text
    assert "[d] diff" in full_text
    assert "Claire:" in full_text
    assert "This will permanently delete the file." in full_text
    assert "Are you sure?" in full_text
    assert "(Esc to cancel)" in full_text

def test_file_tree_overlay_fidelity():
    """Verify File Tree overlay visual composition matching TUI-DESIGN.md Section 11 reference."""
    tree = FileTreeOverlay()
    lines = tree.render(mode=TerminalMode.FULL, width=58)
    full_text = "\n".join(lines)

    assert "╭─ Files " in lines[0]
    assert " x ─╮" in lines[0]
    assert "claire-speech-engine/" in full_text
    assert "└─ src/" in full_text
    assert "├─ decoder.py" in full_text
    assert "M" in full_text
    assert "├─ router.py" in full_text
    assert "+" in full_text
    assert "M modified   + new   plain = untouched" in full_text

def test_review_overlay_fidelity():
    """Verify Review changes overlay visual composition matching TUI-DESIGN.md Section 12 reference."""
    lines = render_preview("review", use_color=False)
    full_text = "\n".join(lines)

    assert "Changes this session" in full_text
    assert "src/decoder.py" in full_text
    assert "+18 -4" in full_text
    assert "src/router.py" in full_text
    assert "(new)" in full_text
    assert "tests/test_decoder.py" in full_text
    assert "3 files changed" in full_text
    assert "46 insertions(+)" in full_text
    assert "4 deletions(-)" in full_text
    assert "[enter] view diff" in full_text
    assert "[c] commit" in full_text
    assert "[q] back" in full_text

def test_task_view_overlay_fidelity():
    """Verify Task / Workflow overlay visual composition matching TUI-DESIGN.md Section 13 reference."""
    task = TaskViewOverlay()
    lines = task.render(mode=TerminalMode.FULL, width=58)
    full_text = "\n".join(lines)

    assert "Current Workflow" in full_text
    assert "Understand objective" in full_text
    assert "Plan changes" in full_text
    assert "Implement changes" in full_text
    assert "Verify" in full_text
    assert "Complete" in full_text
    assert "Task Progress" in full_text
    assert "40%" in full_text
    assert "Objective:" in full_text
    assert "Add streaming decode support with" in full_text

def test_palette_overlay_fidelity():
    """Verify Command Palette overlay visual composition matching TUI-DESIGN.md Section 14 reference."""
    lines = render_preview("palette", use_color=False)
    full_text = "\n".join(lines)

    assert "Commands" in full_text
    assert "APPLICATION / INTERACTION" in full_text
    assert "/help" in full_text
    assert "/status" in full_text
    assert "/model" in full_text
    assert "/mode" in full_text
    assert "/session" in full_text
    assert "/plan" in full_text
    assert "UI / PRESENTATION" in full_text
    assert "/tree" in full_text
    assert "/review" in full_text
    assert "/compact" in full_text
    assert "Type / or ? to open this menu" in full_text

def test_full_vs_compact_vs_minimal_composition():
    """Verify layout across Full, Compact, and Minimal modes."""
    app = create_preview_app()

    # FULL mode
    app.resize(100, 30)
    full_lines = app.render()
    full_str = "\n".join(full_lines)
    assert "╭─ ClaireCoder" in full_str
    assert "╰" in full_str

    # COMPACT mode
    app.resize(80, 24)
    compact_lines = app.render()
    compact_str = "\n".join(compact_lines)
    assert "dir: ~/projects/claire-speech-engine" in compact_str
    assert "> add support for interrupting mid-stream" in compact_str

    # MINIMAL mode
    app.resize(60, 20)
    minimal_lines = app.render()
    minimal_str = "\n".join(minimal_lines)
    assert "--- ClaireCoder (v0.1.0) [IMPLEMENT] ---" in minimal_str
    assert "> add support for interrupting mid-stream" in minimal_str
