"""Native clipboard integration for TUI inputs and wizard fields.

Provides zero-dependency Windows clipboard access via ctypes (user32/kernel32)
without launching external subprocesses (e.g. powershell) or producing visible
terminal output. Includes safe cross-platform fallbacks and text normalization.
"""
import sys
from typing import Optional


def get_clipboard_text() -> str:
    """Reads unicode text from the system clipboard.
    
    On Windows: uses native Win32 API via ctypes (OpenClipboard, GetClipboardData).
    On POSIX: falls back to tkinter if available, otherwise returns empty string.
    
    Returns:
        Clipboard string contents, or empty string on error / empty clipboard.
    """
    if sys.platform == "win32":
        return _get_clipboard_windows()
    else:
        return _get_clipboard_posix()


def _get_clipboard_windows() -> str:
    """Native Windows clipboard reader using ctypes."""
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        CF_UNICODETEXT = 13

        # OpenClipboard takes HWND (NULL/None is valid)
        if not user32.OpenClipboard(None):
            return ""

        try:
            h_clip_mem = user32.GetClipboardData(CF_UNICODETEXT)
            if not h_clip_mem:
                return ""

            kernel32.GlobalLock.restype = wintypes.LPVOID
            p_clip = kernel32.GlobalLock(h_clip_mem)
            if not p_clip:
                return ""

            try:
                text = ctypes.c_wchar_p(p_clip).value
                return text or ""
            finally:
                kernel32.GlobalUnlock(h_clip_mem)
        finally:
            user32.CloseClipboard()
    except Exception:
        return ""


def _get_clipboard_posix() -> str:
    """POSIX fallback for clipboard reading."""
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            text = root.clipboard_get()
            return text or ""
        finally:
            root.destroy()
    except Exception:
        return ""


def normalize_clipboard_text(text: str, single_line: bool = True) -> str:
    """Normalizes clipboard text for single-line or multi-line input fields.
    
    Args:
        text: Raw clipboard text.
        single_line: If True, strips newlines/tabs and collapses whitespace.
        
    Returns:
        Clean normalized text string.
    """
    if not text:
        return ""
    if single_line:
        return " ".join(text.split())
    return text.strip("\r\n")
