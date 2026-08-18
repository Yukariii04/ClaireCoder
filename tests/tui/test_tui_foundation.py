"""Tests for the TUI foundation layer."""
import pytest
from clairecoder.tui.app import TuiApplication
from clairecoder.tui.states import InputState, TerminalMode
from clairecoder.tui.terminal import TerminalCapability

def test_tui_initialization():
    app = TuiApplication()
    assert not app.running
    assert app.state == InputState.NORMAL

def test_tui_start_stop():
    app = TuiApplication()
    app.start()
    assert app.running
    assert app.state == InputState.NORMAL
    
    app.stop()
    assert not app.running
    assert app.state == InputState.EXITING

def test_terminal_capability_and_modes():
    # 96+ columns -> FULL mode
    term = TerminalCapability(width=120, height=40)
    assert term.determine_mode() == TerminalMode.FULL
    
    term.resize(96, 30)
    assert term.determine_mode() == TerminalMode.FULL

    # 76-95 columns -> COMPACT mode
    term.resize(80, 24)
    assert term.determine_mode() == TerminalMode.COMPACT

    term.resize(76, 24)
    assert term.determine_mode() == TerminalMode.COMPACT
    
    # below 76 columns -> MINIMAL mode
    term.resize(75, 20)
    assert term.determine_mode() == TerminalMode.MINIMAL

    term.resize(50, 15)
    assert term.determine_mode() == TerminalMode.MINIMAL

def test_transcript_scrollback():
    from clairecoder.tui.activity import ActivityModel
    app = TuiApplication()
    app.resize(80, 16)
    app.transcript.resize(10)
    
    for i in range(15):
        app.transcript.append_activity(ActivityModel(title=f"Line {i}"))
        
    assert len(app.transcript.activities) == 15
    assert app.transcript.scroll_position == 5
    
    app.transcript.scroll_up(2)
    assert app.transcript.scroll_position == 3
    
    app.transcript.scroll_down(5)
    assert app.transcript.scroll_position == 5

def test_prompt_input_and_submission():
    app = TuiApplication()
    submitted = []
    
    def on_submit(text: str):
        submitted.append(text)
        
    app.prompt.on_submit = on_submit
    
    app.prompt.type_text("hello")
    app.prompt.handle_enter()
    
    assert len(submitted) == 1
    assert submitted[0] == "hello"
    assert app.prompt.content == ""

def test_prompt_suspension_on_overlay():
    app = TuiApplication()
    app.set_state(InputState.OVERLAY)
    
    assert app.prompt.suspended
    app.prompt.type_text("hello")
    assert app.prompt.content == ""  # Should not accept input

def test_escape_ui_behavior():
    app = TuiApplication()
    app.set_state(InputState.OVERLAY)
    
    # Esc should close overlay and return to normal
    app.prompt.handle_escape()
    assert app.state == InputState.NORMAL

def test_ctrl_c_interruption():
    app = TuiApplication()
    interrupted = [False]
    
    def on_interrupt():
        interrupted[0] = True
        
    app.on_interrupt = on_interrupt
    app.handle_ctrl_c()
    
    assert interrupted[0]
