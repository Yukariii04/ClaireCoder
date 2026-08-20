"""Startup and loading boot screen conforming to TUI-DESIGN.md Section 10."""
from typing import List, Optional
from .canvas import visible_length, visible_slice

class LoadingScreen:
    """Renders the full visual composition of the startup/boot screen without graphical mascot artwork."""

    CHECKLIST_ITEMS = [
        "Loading configuration",
        "Connecting model gateway",
        "Registering tools",
        "Preparing workspace",
        "Loading skills",
        "Starting session",
    ]

    QUOTE_TEXT = '"Let\'s build something amazing together."'
    QUOTE_AUTHOR = "- Claire"

    # Stylized 2-line mini block wordmark: CLAIRE (Cyan) + CODER (Pink/Magenta)
    WORDMARK_L1_CLAIRE = "█▀▀ █   ▄▀█ █ █▀█ █▀▀"
    WORDMARK_L1_CODER  = "█▀▀ █▀█ █▀▄ █▀▀ █▀█"
    WORDMARK_L2_CLAIRE = "█▄▄ █▄▄ █▀█ █ █▀▄ ██▄"
    WORDMARK_L2_CODER  = "█▄▄ █▄█ █▄▀ ██▄ █▀▄"

    @staticmethod
    def render(
        width: int = 56,
        height: int = 38,
        use_color: bool = True,
        checklist_items: Optional[List[object]] = None,
        progress_pct: int = 100,
        status_text: str = "Launching..."
    ) -> List[str]:
        """Renders the complete loading screen frame with stylized CLAIRECODER branding wordmark."""
        frame_w = max(48, min(width, 60))
        inner_w = frame_w - 4

        # ANSI Colors for locked ClaireCoder palette
        CYAN = "\x1b[38;2;0;229;255m\x1b[1m" if use_color else ""
        PINK = "\x1b[38;2;255;45;120m\x1b[1m" if use_color else ""
        MUTED_CYAN = "\x1b[38;2;140;220;240m" if use_color else ""
        GREEN = "\x1b[38;2;80;250;123m\x1b[1m" if use_color else ""
        YELLOW = "\x1b[38;2;241;250;140m" if use_color else ""
        WHITE = "\x1b[37m" if use_color else ""
        RESET = "\x1b[0m" if use_color else ""

        def frame_line(content: str = "", align: str = "left") -> str:
            vis_len = visible_length(content)
            if vis_len > inner_w:
                content = visible_slice(content, 0, inner_w)
                vis_len = visible_length(content)

            if align == "center":
                pad_total = max(0, inner_w - vis_len)
                pad_l = pad_total // 2
                pad_r = pad_total - pad_l
                return f"│ {' ' * pad_l}{content}{' ' * pad_r} │"
            elif align == "right":
                pad_l = max(0, inner_w - vis_len)
                return f"│ {' ' * pad_l}{content} │"
            else:
                pad_r = max(0, inner_w - vis_len)
                return f"│ {content}{' ' * pad_r} │"

        lines: List[str] = []

        # Top border with CLAIRECODER title (exact width frame_w)
        top_bar = f"╭─ CLAIRECODER " + ("─" * max(0, frame_w - 17)) + "─╮"
        lines.append(top_bar)
        lines.append(frame_line(""))

        # 1. Stylized 2-line mini block wordmark in ClaireCoder cyan & pink palette
        wm_l1 = f"{CYAN}{LoadingScreen.WORDMARK_L1_CLAIRE}{RESET}   {PINK}{LoadingScreen.WORDMARK_L1_CODER}{RESET}"
        wm_l2 = f"{CYAN}{LoadingScreen.WORDMARK_L2_CLAIRE}{RESET}   {PINK}{LoadingScreen.WORDMARK_L2_CODER}{RESET}"

        lines.append(frame_line(wm_l1, align="center"))
        lines.append(frame_line(wm_l2, align="center"))

        # Subtitle: Engineering. Automated.
        sub = f"{MUTED_CYAN}Engineering. Automated.{RESET}" if use_color else "Engineering. Automated."
        lines.append(frame_line(sub, align="center"))
        lines.append(frame_line(""))

        # Subtitle message
        init_msg = f"{WHITE}Initializing ClaireCoder Engine...{RESET}" if use_color else "Initializing ClaireCoder Engine..."
        lines.append(frame_line(init_msg, align="center"))
        lines.append(frame_line(""))

        # Checklist rendering with real status badges and strictly bounded row widths
        items_to_render = checklist_items if checklist_items is not None else [(item, "OK") for item in LoadingScreen.CHECKLIST_ITEMS]

        for item_entry in items_to_render:
            if isinstance(item_entry, (tuple, list)):
                item_name, status = item_entry[0], item_entry[1]
            else:
                item_name, status = str(item_entry), "OK"

            status_upper = str(status).upper()
            if status_upper == "OK":
                badge_text = "[ OK ]"
                badge = f"{GREEN}[ OK ]{RESET}" if use_color else "[ OK ]"
            elif status_upper in ("NOT CONFIGURED", "UNCONFIGURED"):
                badge_text = "[ NOT CONFIGURED ]"
                badge = f"{YELLOW}[ NOT CONFIGURED ]{RESET}" if use_color else "[ NOT CONFIGURED ]"
            elif status_upper == "RUNNING":
                badge_text = "[ ... ]"
                badge = f"{CYAN}[ ... ]{RESET}" if use_color else "[ ... ]"
            elif status_upper == "FAIL":
                badge_text = "[ FAIL ]"
                badge = f"{PINK}[ FAIL ]{RESET}" if use_color else "[ FAIL ]"
            else:
                badge_text = "[     ]"
                badge = "[     ]"

            # Bounded item length accounting: 2 (indent "  ") + 2 (prefix "> ") + vis(item_name) + dots (min 2) + badge_len <= inner_w
            badge_len = visible_length(badge_text)
            avail_for_name = inner_w - 4 - badge_len - 2
            item_display = str(item_name)
            if visible_length(item_display) > avail_for_name:
                item_display = visible_slice(item_display, 0, max(4, avail_for_name))

            dot_space = max(2, inner_w - 4 - visible_length(item_display) - badge_len)
            dots = " " * dot_space
            check_str = f"> {item_display}{dots}{badge}"
            lines.append(frame_line(f"  {check_str}"))

        lines.append(frame_line(""))

        # Dynamic progress bar calculation (Bug A & B resolution)
        pct = max(0, min(100, progress_pct))
        pct_str = f"{pct}%"
        fixed_spacing = 4  # 2 (leading indent "  ") + 1 (space before bar) + 1 (space before pct)
        status_vis = visible_length(status_text)
        avail_bar_w = inner_w - fixed_spacing - status_vis - len(pct_str)

        if avail_bar_w < 6:
            max_status_len = max(6, inner_w - fixed_spacing - 8 - len(pct_str))
            status_display = visible_slice(status_text, 0, max_status_len)
            status_vis = visible_length(status_display)
            avail_bar_w = max(4, inner_w - fixed_spacing - status_vis - len(pct_str))
        else:
            status_display = status_text

        bar_len = avail_bar_w
        filled_count = int(bar_len * pct / 100)
        empty_count = max(0, bar_len - filled_count)

        if use_color:
            mid = min(filled_count, bar_len // 2)
            rem = filled_count - mid
            filled_bar = f"{CYAN}{'█' * mid}{PINK}{'█' * rem}{RESET}{'░' * empty_count}"
            prog_str = f"{CYAN}{status_display}{RESET} {filled_bar} {PINK}{pct_str}{RESET}"
        else:
            filled_bar = ("█" * filled_count) + ("░" * empty_count)
            prog_str = f"{status_display} {filled_bar} {pct_str}"

        lines.append(frame_line(f"  {prog_str}"))
        lines.append(frame_line(""))

        # Quote card at bottom
        quote_card_w = min(frame_w - 8, 48)
        q_inner_w = quote_card_w - 4
        q_top = "╭" + ("─" * (quote_card_w - 2)) + "╮"
        q_bot = "╰" + ("─" * (quote_card_w - 2)) + "╯"

        q1_text = f"{MUTED_CYAN}{LoadingScreen.QUOTE_TEXT}{RESET}" if use_color else LoadingScreen.QUOTE_TEXT
        if visible_length(q1_text) > q_inner_w:
            q1_text = visible_slice(q1_text, 0, q_inner_w)
        q1_vis = visible_length(q1_text)
        q1_pad = max(0, q_inner_w - q1_vis)
        q_line1 = f"│ {q1_text}{' ' * q1_pad} │"

        q2_text = f"{PINK}{LoadingScreen.QUOTE_AUTHOR}{RESET}" if use_color else LoadingScreen.QUOTE_AUTHOR
        if visible_length(q2_text) > q_inner_w:
            q2_text = visible_slice(q2_text, 0, q_inner_w)
        q2_vis = visible_length(q2_text)
        q2_pad = max(0, q_inner_w - q2_vis)
        q_line2 = f"│ {' ' * q2_pad}{q2_text} │"

        lines.append(frame_line(q_top, align="center"))
        lines.append(frame_line(q_line1, align="center"))
        lines.append(frame_line(q_line2, align="center"))
        lines.append(frame_line(q_bot, align="center"))

        lines.append(frame_line(""))
        # Bottom border (exact width frame_w)
        lines.append("╰" + ("─" * (frame_w - 2)) + "╯")

        return lines
