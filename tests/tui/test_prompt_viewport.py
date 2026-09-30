"""Tests for PromptInput cursor-aware viewport and navigation."""
import pytest
from clairecoder.tui.prompt import PromptInput
from clairecoder.tui.canvas import visible_length


def test_prompt_input_basic_typing_and_cursor():
    p = PromptInput()
    p.type_text("hello")
    assert p.get_text() == "hello"
    assert p.cursor_pos == 5

    p.move_cursor_left(2)
    assert p.cursor_pos == 3

    p.insert_char("X")
    assert p.get_text() == "helXlo"
    assert p.cursor_pos == 4

    p.backspace()
    assert p.get_text() == "hello"
    assert p.cursor_pos == 3

    p.delete_char()
    assert p.get_text() == "helo"
    assert p.cursor_pos == 3


def test_prompt_input_home_and_end():
    p = PromptInput()
    p.set_text("super long line of text")
    assert p.cursor_pos == len("super long line of text")

    p.move_cursor_home()
    assert p.cursor_pos == 0

    p.move_cursor_end()
    assert p.cursor_pos == len("super long line of text")


def test_prompt_viewport_short_text():
    p = PromptInput()
    p.set_text("short")
    rendered = p.render_line(available_width=40, focused=True)
    assert rendered == "> short█"
    assert visible_length(rendered) <= 40


def test_prompt_viewport_long_text_cursor_tracking():
    p = PromptInput()
    long_text = "This is a very long command prompt that extends way past normal terminal column limits"
    p.set_text(long_text)
    
    # Cursor at the end: viewport must show the tail including the cursor
    rendered_end = p.render_line(available_width=30, focused=True)
    assert "█" in rendered_end
    assert visible_length(rendered_end) <= 30
    assert rendered_end.startswith("> ")
    assert "limits" in rendered_end

    # Move cursor to start: viewport must show the head including the cursor
    p.move_cursor_home()
    rendered_home = p.render_line(available_width=30, focused=True)
    assert "█" in rendered_home
    assert visible_length(rendered_home) <= 30
    assert rendered_home.startswith("> █This")


def test_prompt_submit_clears_text_and_cursor():
    p = PromptInput()
    submitted = []
    p.on_submit = lambda s: submitted.append(s)
    p.set_text("my command")
    p.handle_enter()

    assert submitted == ["my command"]
    assert p.get_text() == ""
    assert p.cursor_pos == 0
