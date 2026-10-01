"""Terminal capability, rendering, and input abstractions."""
import sys
from typing import Any, List, Optional, TextIO, Tuple

from .states import TerminalMode


class TerminalCapability:
    """Abstracts terminal capabilities and size."""

    def __init__(
        self,
        width: Optional[int] = None,
        height: Optional[int] = None,
        mode: Optional[TerminalMode] = None,
    ) -> None:
        if width is None or height is None:
            import shutil
            cols, rows = shutil.get_terminal_size((104, 30))
            self.width = width if width is not None else cols
            self.height = height if height is not None else rows
        else:
            self.width = width
            self.height = height
        self.colors = True
        self.mode = mode

    def get_size(self) -> Tuple[int, int]:
        return self.width, self.height

    def resize(self, width: int, height: int) -> None:
        """Handle terminal resize."""
        self.width = width
        self.height = height

    def force_mode(self, mode: TerminalMode) -> None:
        """Explicitly override the automatic mode."""
        self.mode = mode

    def determine_mode(self) -> TerminalMode:
        """Determine TUI mode based on capability or forced override.

        Target adaptation hierarchy (CC-PRD-011 §26, TUI-DESIGN.md §26):
            96+ columns               -> Full TUI
            approximately 76-95 cols  -> Compact TUI
            below ~76 cols            -> Minimal TUI
        """
        if self.mode is not None:
            return self.mode
        if self.width < 76:
            return TerminalMode.MINIMAL
        elif self.width < 96:
            return TerminalMode.COMPACT
        else:
            return TerminalMode.FULL


class TerminalRenderer:
    """Handles in-place terminal frame redrawing without scrollback accumulation."""

    def __init__(
        self, stream: Optional[TextIO] = None, enable_ansi: bool = True
    ) -> None:
        self.stream: TextIO = stream if stream is not None else sys.stdout
        self.enable_ansi: bool = enable_ansi
        self.last_line_count: int = 0
        self.rendered_frames_count: int = 0
        self._history: List[List[str]] = []

        if hasattr(self.stream, "reconfigure"):
            try:
                self.stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

    def _write_safe(self, text: str) -> None:
        try:
            self.stream.write(text)
        except (UnicodeEncodeError, OSError):
            if hasattr(self.stream, "buffer"):
                try:
                    self.stream.buffer.write(text.encode("utf-8", errors="replace"))
                except Exception:
                    pass
            else:
                try:
                    self.stream.write(text.encode("ascii", errors="replace").decode("ascii"))
                except Exception:
                    pass

    def render_frame(self, lines: List[str]) -> None:
        """First or fresh full render of a frame."""
        self._history.append(list(lines))
        self.rendered_frames_count += 1
        output = "\n".join(lines)
        self._write_safe(output)
        try:
            self.stream.flush()
        except Exception:
            pass
        self.last_line_count = len(lines)

    def redraw(self, lines: List[str]) -> None:
        """Redraws the current frame in-place over the previous frame."""
        self._history.append(list(lines))
        self.rendered_frames_count += 1

        if not self.enable_ansi or self.last_line_count == 0:
            self.render_frame(lines)
            return

        # Move cursor up to the first line of the previous frame and to column 0
        if self.last_line_count > 1:
            reposition = f"\x1b[{self.last_line_count - 1}A\r"
        else:
            reposition = "\r"

        clear_rest = "\x1b[J"
        output = "\n".join(lines)

        self._write_safe(reposition + clear_rest + output)
        try:
            self.stream.flush()
        except Exception:
            pass
        self.last_line_count = len(lines)

    def clear(self) -> None:
        """Clear active terminal frame, reset styling and restore cursor."""
        if self.enable_ansi and self.last_line_count > 0:
            if self.last_line_count > 1:
                reposition = f"\x1b[{self.last_line_count - 1}A\r"
            else:
                reposition = "\r"
            self._write_safe(f"{reposition}\x1b[J\x1b[0m\x1b[?25h")
            try:
                self.stream.flush()
            except Exception:
                pass
            self.last_line_count = 0


class KeyEvent:
    """Represents a decoded key event from terminal input."""

    def __init__(
        self,
        name: str,
        char: Optional[str] = None,
        is_printable: bool = False,
        raw: str = "",
    ) -> None:
        self.name: str = name
        self.char: Optional[str] = char
        self.is_printable: bool = is_printable
        self.raw: str = raw

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"KeyEvent({self.name!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.name.lower() == other.lower()
        if isinstance(other, KeyEvent):
            return self.name.lower() == other.name.lower()
        return False

    def __hash__(self) -> int:
        return hash(self.name.lower())


class InputDecoder:
    """Deterministic terminal input decoder converting raw sequences to KeyEvents."""

    # VT / ANSI escape sequences
    VT_SEQUENCES = {
        "\x1b[A": "up",
        "\x1bOA": "up",
        "\x1b[B": "down",
        "\x1bOB": "down",
        "\x1b[C": "right",
        "\x1bOC": "right",
        "\x1b[D": "left",
        "\x1bOD": "left",
        "\x1b[H": "home",
        "\x1b[1~": "home",
        "\x1bOH": "home",
        "\x1b[F": "end",
        "\x1b[4~": "end",
        "\x1bOF": "end",
        "\x1b[5~": "pageup",
        "\x1b[I": "pageup",
        "\x1b[6~": "pagedown",
        "\x1b[Q": "pagedown",
        "\x1b[2~": "insert",
        "\x1b[3~": "delete",
        "\x1b[Z": "backtab",
    }

    # Classic Windows console scan codes (prefixed with \x00 or \xe0)
    SCAN_CODES = {
        "H": "up",
        "P": "down",
        "K": "left",
        "M": "right",
        "I": "pageup",
        "Q": "pagedown",
        "G": "home",
        "O": "end",
        "S": "delete",
        "R": "insert",
    }

    # Named / control character mappings
    CONTROL_MAP = {
        "\r": "enter",
        "\n": "enter",
        "\x08": "backspace",
        "\x7f": "backspace",
        "\t": "tab",
        "\x1b": "escape",
        "\x03": "ctrl+c",
        "\x14": "ctrl+t",
        "\x12": "ctrl+r",
        "\x10": "ctrl+p",
        "\x16": "ctrl+v",
    }

    # Canonical named key aliases
    NAMED_KEYS = {
        "up", "down", "left", "right",
        "pageup", "page_up", "pgup",
        "pagedown", "page_down", "pgdn",
        "home", "end", "insert", "delete",
        "enter", "return", "backspace", "tab",
        "escape", "esc",
        "ctrl+c", "ctrl+t", "ctrl+r", "ctrl+p", "ctrl+v",
        "shift+insert", "shift_insert", "paste",
    }

    @classmethod
    def decode(cls, raw: Any) -> KeyEvent:
        """Deterministically decodes raw input into a KeyEvent."""
        if isinstance(raw, KeyEvent):
            return raw

        if not isinstance(raw, str):
            raw = str(raw) if raw is not None else ""

        if not raw:
            return KeyEvent("unknown", raw="")

        clean_lower = raw.strip().lower()

        # Check known canonical named keys
        if clean_lower in cls.NAMED_KEYS:
            normalized = clean_lower
            if normalized in ("page_up", "pgup"):
                normalized = "pageup"
            elif normalized in ("page_down", "pgdn"):
                normalized = "pagedown"
            elif normalized in ("return",):
                normalized = "enter"
            elif normalized in ("esc",):
                normalized = "escape"
            elif normalized in ("paste", "ctrl_v"):
                normalized = "ctrl+v"
            elif normalized in ("shift_insert",):
                normalized = "shift+insert"
            return KeyEvent(normalized, raw=raw)

        # Check VT escape sequences
        if raw.startswith("\x1b"):
            if raw in cls.VT_SEQUENCES:
                return KeyEvent(cls.VT_SEQUENCES[raw], raw=raw)
            if len(raw) == 1:
                return KeyEvent("escape", raw=raw)
            # Unrecognized escape sequence -> NEVER treat as printable text
            return KeyEvent("unknown", raw=raw)

        # Check Windows classic scan codes (\x00 or \xe0 prefix)
        if len(raw) >= 2 and raw[0] in ("\x00", "\xe0"):
            code = raw[1:]
            if code in cls.SCAN_CODES:
                return KeyEvent(cls.SCAN_CODES[code], raw=raw)
            return KeyEvent("unknown", raw=raw)

        # Check control characters
        if raw in cls.CONTROL_MAP:
            return KeyEvent(cls.CONTROL_MAP[raw], raw=raw)

        # Single printable character
        if len(raw) == 1 and raw.isprintable():
            return KeyEvent(raw, char=raw, is_printable=True, raw=raw)

        # Multi-character strings (e.g. pasted or scripted command line)
        return KeyEvent(raw, raw=raw)


class TerminalInput:
    """Handles character-by-character non-echoing console input across Windows and POSIX."""

    def __init__(self, input_source: Optional[Any] = None) -> None:
        self.input_source = input_source
        self._iter = iter(input_source) if input_source is not None else None

    def read_key(self) -> Optional[KeyEvent]:
        """Reads a single key, shortcut event, or scripted command.

        Returns:
            - A KeyEvent representing the key.
            - None on EOF or end of input source.
        """
        if self._iter is not None:
            try:
                item = next(self._iter)
                if item is None:
                    return None
                return InputDecoder.decode(item)
            except StopIteration:
                return None

        # Live native terminal input
        if sys.platform == "win32":
            return self._read_key_windows()
        else:
            return self._read_key_posix()

    def read_key_timeout(self, timeout: float = 0.03) -> Optional[KeyEvent]:
        """Reads a key with a timeout; returns None if no input arrives within timeout.
        
        Allows the TUI loop to process asynchronous background events and perform
        single-owner redrawing without blocking indefinitely.
        """
        if self._iter is not None:
            return self.read_key()

        if sys.platform == "win32":
            if not sys.stdin.isatty():
                return self._read_key_windows()
            import msvcrt
            import time
            start = time.time()
            while time.time() - start < timeout:
                if msvcrt.kbhit():
                    return self._read_key_windows()
                time.sleep(0.005)
            return None
        else:
            if not sys.stdin.isatty():
                return self._read_key_posix()
            import select
            r, _, _ = select.select([sys.stdin], [], [], timeout)
            if r:
                return self._read_key_posix()
            return None

    def _read_key_windows(self) -> Optional[KeyEvent]:
        # If stdin is redirected / not a tty (e.g. subprocess pipe or CI), read from sys.stdin
        if not sys.stdin.isatty():
            try:
                ch = sys.stdin.read(1)
                if not ch or ch == "\x04":
                    return None
                return InputDecoder.decode(ch)
            except Exception:
                return None

        import msvcrt
        import time

        try:
            ch = msvcrt.getwch()
        except (EOFError, OSError):
            return None

        # Check special prefix characters (0x00 or 0xE0)
        if ch in ("\x00", "\xe0"):
            try:
                ch2 = msvcrt.getwch()
                return InputDecoder.decode(ch + ch2)
            except Exception:
                return None

        # Check VT/ANSI Escape sequence
        if ch == "\x1b":
            seq = ch
            start_time = time.time()
            while time.time() - start_time < 0.05:
                if msvcrt.kbhit():
                    try:
                        next_ch = msvcrt.getwch()
                        seq += next_ch
                        if len(seq) >= 3 and (next_ch.isalpha() or next_ch == "~"):
                            break
                    except Exception:
                        break
                else:
                    if len(seq) > 1:
                        time.sleep(0.002)
                    else:
                        time.sleep(0.005)
                        if not msvcrt.kbhit():
                            break
            return InputDecoder.decode(seq)

        if ch == "\x04":
            return None

        return InputDecoder.decode(ch)

    def _read_key_posix(self) -> Optional[KeyEvent]:
        import select
        import termios
        import tty

        fd = sys.stdin.fileno()
        try:
            old_settings = termios.tcgetattr(fd)
        except Exception:
            try:
                ch = sys.stdin.read(1)
                if not ch or ch == "\x04":
                    return None
                return InputDecoder.decode(ch)
            except Exception:
                return None

        try:
            tty.setcbreak(fd)
            ch = sys.stdin.read(1)
            if not ch or ch == "\x04":
                return None
            if ch == "\x1b":
                seq = ch
                r, _, _ = select.select([sys.stdin], [], [], 0.05)
                if r:
                    seq += sys.stdin.read(2)
                    if seq in ("\x1b[5", "\x1b[6", "\x1b[1", "\x1b[4", "\x1b[2", "\x1b[3"):
                        r3, _, _ = select.select([sys.stdin], [], [], 0.02)
                        if r3:
                            seq += sys.stdin.read(1)
                return InputDecoder.decode(seq)
            return InputDecoder.decode(ch)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
