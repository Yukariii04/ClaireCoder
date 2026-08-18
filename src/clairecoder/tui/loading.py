"""Startup and loading boot screen conforming to TUI-DESIGN.md Section 10."""
from typing import List, Optional
from .canvas import visible_length

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
    def render(width: int = 56, height: int = 38, use_color: bool = True) -> List[str]:
        """Renders the complete loading screen frame with stylized CLAIRECODER branding wordmark."""
        frame_w = max(48, min(width, 60))
        inner_w = frame_w - 4

        # ANSI Colors for locked ClaireCoder palette
        CYAN = "\x1b[38;2;0;229;255m\x1b[1m" if use_color else ""
        PINK = "\x1b[38;2;255;45;120m\x1b[1m" if use_color else ""
        MUTED_CYAN = "\x1b[38;2;140;220;240m" if use_color else ""
        GREEN = "\x1b[38;2;80;250;123m\x1b[1m" if use_color else ""
        WHITE = "\x1b[37m" if use_color else ""
        RESET = "\x1b[0m" if use_color else ""

        def frame_line(content: str = "", align: str = "left") -> str:
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

        # Top border with CLAIRECODER title
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

        # Checklist
        for item in LoadingScreen.CHECKLIST_ITEMS:
            dot_space = inner_w - len(item) - 14
            dots = " " * max(2, dot_space)
            ok_badge = f"{GREEN}[ OK ]{RESET}" if use_color else "[ OK ]"
            check_str = f"> {item}{dots}{ok_badge}"
            lines.append(frame_line(f"  {check_str}"))

        lines.append(frame_line(""))

        # Progress bar
        bar_len = max(10, inner_w - 22)
        if use_color:
            mid = bar_len // 2
            filled_bar = f"{CYAN}{'█' * mid}{PINK}{'█' * (bar_len - mid)}{RESET}"
            prog_str = f"{CYAN}Launching...{RESET} {filled_bar} {PINK}100%{RESET}"
        else:
            filled_bar = "█" * bar_len
            prog_str = f"Launching... {filled_bar} 100%"
        lines.append(frame_line(f"  {prog_str}"))
        lines.append(frame_line(""))

        # Quote card at bottom
        quote_card_w = min(frame_w - 8, 48)
        q_inner_w = quote_card_w - 4
        q_top = "╭" + ("─" * (quote_card_w - 2)) + "╮"
        q_bot = "╰" + ("─" * (quote_card_w - 2)) + "╯"

        q1_text = f"{MUTED_CYAN}{LoadingScreen.QUOTE_TEXT}{RESET}" if use_color else LoadingScreen.QUOTE_TEXT
        q1_vis = visible_length(q1_text)
        q1_pad = max(0, q_inner_w - q1_vis)
        q_line1 = f"│ {q1_text}{' ' * q1_pad} │"

        q2_text = f"{PINK}{LoadingScreen.QUOTE_AUTHOR}{RESET}" if use_color else LoadingScreen.QUOTE_AUTHOR
        q2_vis = visible_length(q2_text)
        q2_pad = max(0, q_inner_w - q2_vis)
        q_line2 = f"│ {' ' * q2_pad}{q2_text} │"

        lines.append(frame_line(q_top, align="center"))
        lines.append(frame_line(q_line1, align="center"))
        lines.append(frame_line(q_line2, align="center"))
        lines.append(frame_line(q_bot, align="center"))

        lines.append(frame_line(""))
        # Bottom border
        lines.append("╰" + ("─" * (frame_w - 2)) + "╯")

        return lines
