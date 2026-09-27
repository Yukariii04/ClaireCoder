"""First-run Setup Wizard for TUI provider/model configuration.

Implements the wizard state machine per Stage 7 §8:
    Provider Selection → Credential Entry → Validation →
    Model Discovery → Model Selection → Capability View →
    Skill Selection → Final Summary → Save

The wizard renders within the TUI frame and completely disappears
before the Loading Screen begins.
"""
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from clairecoder.gateway.config import (
    PROVIDER_REGISTRY, ProviderCategory, ProviderProfile, AdapterType,
)
from .canvas import visible_length, visible_slice


class WizardStage(str, Enum):
    """Sequential wizard stages."""
    PROVIDER_SELECT = "provider_select"
    CREDENTIAL_ENTRY = "credential_entry"
    VALIDATING = "validating"
    DISCOVERING = "discovering"
    MODEL_SELECT = "model_select"
    CAPABILITY_VIEW = "capability_view"
    SKILL_SELECT = "skill_select"
    SUMMARY = "summary"
    SAVING = "saving"
    COMPLETE = "complete"
    ERROR = "error"


class WizardCardGeometry:
    """Authoritative geometry calculator and line builder for wizard cards.

    Guarantees:
      - card_width <= available terminal width
      - len(top_border) == len(body_row) == len(bottom_border) == len(divider) == card_width
      - ANSI-aware length and slice handling
    """

    def __init__(self, available_width: int = 80, max_card_width: int = 64, min_card_width: int = 36) -> None:
        self.available_width = max(min_card_width, available_width)
        target_w = min(self.available_width, max_card_width)
        # Inner width is target_w minus left/right borders ("│ " and " │" = 4 chars)
        self.inner_width = max(10, target_w - 4)
        # Total card width is inner_width + 4 chars
        self.card_width = self.inner_width + 4

    def top_border(self, title: Optional[str] = None) -> str:
        """Render the top border with optional title header."""
        if not title:
            return f"╭{'─' * (self.card_width - 2)}╮"
        prefix = f"╭─ {title} "
        vis_prefix = visible_length(prefix)
        if vis_prefix >= self.card_width - 2:
            # Title too long for card; truncate cleanly
            max_title_len = max(3, self.card_width - 9)
            title = title[:max_title_len - 3] + "..."
            prefix = f"╭─ {title} "
            vis_prefix = visible_length(prefix)
        dashes_count = max(0, (self.card_width - 1) - vis_prefix)
        return f"{prefix}{'─' * dashes_count}╮"

    def row(self, text: str = "") -> str:
        """Render a single framed body row padded or clipped to inner_width."""
        vis = visible_length(text)
        if vis > self.inner_width:
            text = visible_slice(text, 0, self.inner_width)
            vis = visible_length(text)
        pad = max(0, self.inner_width - vis)
        return f"│ {text}{' ' * pad} │"

    def empty_row(self) -> str:
        """Render an empty framed row."""
        return self.row("")

    def divider(self) -> str:
        """Render a horizontal divider."""
        return f"├{'─' * (self.card_width - 2)}┤"

    def bottom_border(self) -> str:
        """Render the bottom border."""
        return f"╰{'─' * (self.card_width - 2)}╯"

    def wrap_rows(self, text: str, prefix: str = "  ") -> List[str]:
        """Wrap long text into multiple rows fitting within inner_width."""
        if not text:
            return [self.empty_row()]
        lines = []
        words = text.split(" ")
        current = prefix
        for word in words:
            if not word:
                continue
            test_line = f"{current} {word}" if current != prefix else f"{current}{word}"
            if visible_length(test_line) <= self.inner_width:
                current = test_line
            else:
                if current.strip():
                    lines.append(self.row(current))
                current = f"{prefix}{word}"
        if current.strip():
            lines.append(self.row(current))
        return lines or [self.row(f"{prefix}{text}")]


class SetupWizard:
    """TUI Setup Wizard state machine.

    Manages the staged configuration flow, renders each stage,
    and handles keyboard input within the wizard context.
    """

    def __init__(self) -> None:
        self.stage = WizardStage.PROVIDER_SELECT
        # Provider selection
        self._provider_list: List[Dict[str, Any]] = self._build_provider_list()
        selectable = self._selectable_indices()
        self.selected_index: int = selectable[0] if selectable else 0
        self.viewport_offset: int = 0
        self.viewport_height: int = 8

        # Credential/connection entry
        self.credential_input: str = ""
        self.endpoint_input: str = ""
        self.cursor_pos: int = 0
        self._active_field: str = "credential"  # or "endpoint"

        # Validation/discovery state & request generation tracking
        self.generation: int = 0
        self.active_request_id: Optional[str] = None
        self.validation_error: Optional[str] = None
        self.discovered_models: List[Dict[str, Any]] = []
        self.model_selected_index: int = 0
        self.model_viewport_offset: int = 0

        # Skills
        self.available_skills: List[Dict[str, Any]] = [
            {"id": "code_review", "name": "Code Review", "enabled": True},
            {"id": "testing", "name": "Test Generation", "enabled": True},
            {"id": "documentation", "name": "Documentation", "enabled": False},
            {"id": "refactoring", "name": "Refactoring", "enabled": False},
        ]
        self.skill_selected_index: int = 0

        # Final state
        self.selected_provider: Optional[Dict[str, Any]] = None
        self.selected_model: Optional[Dict[str, Any]] = None
        self.saved_profile_id: Optional[str] = None

        # Callbacks
        self.on_validate: Optional[Callable] = None
        self.on_discover: Optional[Callable] = None
        self.on_save: Optional[Callable] = None

    @property
    def is_complete(self) -> bool:
        return self.stage == WizardStage.COMPLETE

    @property
    def is_active(self) -> bool:
        return self.stage != WizardStage.COMPLETE

    def _build_provider_list(self) -> List[Dict[str, Any]]:
        """Build grouped provider list for selection."""
        hosted = []
        local = []
        custom = []
        for pid, info in PROVIDER_REGISTRY.items():
            entry = {"id": pid, **info}
            cat = info.get("category", ProviderCategory.CUSTOM)
            if cat == ProviderCategory.HOSTED:
                hosted.append(entry)
            elif cat == ProviderCategory.LOCAL:
                local.append(entry)
            else:
                custom.append(entry)
        result: List[Dict[str, Any]] = []
        if hosted:
            result.append({"type": "header", "label": "HOSTED PROVIDERS"})
            result.extend(hosted)
        if local:
            result.append({"type": "header", "label": "LOCAL / SELF-HOSTED"})
            result.extend(local)
        if custom:
            result.append({"type": "header", "label": "CUSTOM"})
            result.extend(custom)
        return result

    def _selectable_indices(self) -> List[int]:
        """Return indices of selectable (non-header) items."""
        return [i for i, item in enumerate(self._provider_list) if item.get("type") != "header"]

    def _current_selectable_pos(self) -> int:
        """Map selected_index to position in selectable items."""
        selectable = self._selectable_indices()
        if self.selected_index in selectable:
            return selectable.index(self.selected_index)
        return 0

    # ── Key Handling ────────────────────────────────────────────────────────

    def handle_key(self, key: str) -> bool:
        """Handle keyboard input for the current wizard stage. Returns True if consumed."""
        clean = key.strip().lower() if key else ""

        if self.stage == WizardStage.PROVIDER_SELECT:
            return self._handle_provider_select(clean)
        elif self.stage == WizardStage.CREDENTIAL_ENTRY:
            return self._handle_credential_entry(key, clean)
        elif self.stage == WizardStage.MODEL_SELECT:
            return self._handle_model_select(clean)
        elif self.stage == WizardStage.CAPABILITY_VIEW:
            if clean in ("enter", "return"):
                self.stage = WizardStage.SKILL_SELECT
                return True
            elif clean in ("escape", "esc"):
                self.stage = WizardStage.MODEL_SELECT
                return True
            return True
        elif self.stage == WizardStage.SKILL_SELECT:
            return self._handle_skill_select(clean)
        elif self.stage == WizardStage.SUMMARY:
            return self._handle_summary(clean)
        elif self.stage == WizardStage.ERROR:
            if clean in ("enter", "return"):
                self.stage = WizardStage.CREDENTIAL_ENTRY
                self.validation_error = None
                return True
            elif clean in ("escape", "esc"):
                self.stage = WizardStage.PROVIDER_SELECT
                self.validation_error = None
                self.active_request_id = None
                return True
            return True

        return True  # Absorb all input during transitional stages

    def _handle_provider_select(self, key: str) -> bool:
        selectable = self._selectable_indices()
        if not selectable:
            return True
        pos = self._current_selectable_pos()

        if key in ("up", "k"):
            new_pos = max(0, pos - 1)
            self.selected_index = selectable[new_pos]
            return True
        elif key in ("down", "j"):
            new_pos = min(len(selectable) - 1, pos + 1)
            self.selected_index = selectable[new_pos]
            return True
        elif key in ("pageup",):
            new_pos = max(0, pos - self.viewport_height)
            self.selected_index = selectable[new_pos]
            return True
        elif key in ("pagedown",):
            new_pos = min(len(selectable) - 1, pos + self.viewport_height)
            self.selected_index = selectable[new_pos]
            return True
        elif key in ("home",):
            self.selected_index = selectable[0]
            return True
        elif key in ("end",):
            self.selected_index = selectable[-1]
            return True
        elif key in ("enter", "return"):
            item = self._provider_list[self.selected_index]
            self.selected_provider = item
            # Pre-fill endpoint
            self.endpoint_input = item.get("default_endpoint", "")
            self.credential_input = ""
            self.cursor_pos = 0
            self._active_field = "credential" if item.get("requires_api_key") else "endpoint"
            self.stage = WizardStage.CREDENTIAL_ENTRY
            return True
        return True

    def _handle_credential_entry(self, raw_key: str, key: str) -> bool:
        if key in ("escape", "esc"):
            self.stage = WizardStage.PROVIDER_SELECT
            self.active_request_id = None
            return True
        elif key in ("ctrl+v", "shift+insert", "paste"):
            from .clipboard import get_clipboard_text, normalize_clipboard_text
            clip = normalize_clipboard_text(get_clipboard_text(), single_line=True)
            if clip:
                if self._active_field == "credential":
                    self.credential_input += clip
                    self.cursor_pos = len(self.credential_input)
                else:
                    self.endpoint_input += clip
                    self.cursor_pos = len(self.endpoint_input)
            return True
        elif key == "tab":
            # Toggle between credential and endpoint fields
            if self._active_field == "credential":
                self._active_field = "endpoint"
                self.cursor_pos = len(self.endpoint_input)
            else:
                self._active_field = "credential"
                self.cursor_pos = len(self.credential_input)
            return True
        elif key in ("enter", "return"):
            self._begin_validation()
            return True
        elif key in ("backspace", "\x7f", "\x08"):
            if self._active_field == "credential":
                if self.credential_input:
                    self.credential_input = self.credential_input[:-1]
            else:
                if self.endpoint_input:
                    self.endpoint_input = self.endpoint_input[:-1]
            return True
        elif len(raw_key) == 1 and raw_key.isprintable():
            if self._active_field == "credential":
                self.credential_input += raw_key
            else:
                self.endpoint_input += raw_key
            return True
        return True

    def _format_error(self, error: Optional[str]) -> str:
        """Format provider errors cleanly with status and provider message, without raw tracebacks or secrets."""
        if not error:
            return "Connection validation failed."
        err = str(error).strip()
        # Remove any potential secrets or authorization tokens
        import re
        err = re.sub(r'Bearer\s+[A-Za-z0-9_\-\.]+', 'Bearer ••••••', err)
        err = re.sub(r'key=[A-Za-z0-9_\-\.]+', 'key=••••••', err)
        err = re.sub(r'x-api-key:\s*[A-Za-z0-9_\-\.]+', 'x-api-key: ••••••', err)

        # Check for HTTP status codes with messages
        if "401" in err or "Unauthorized" in err:
            if "invalid api key" in err.lower():
                return "Invalid API Key (HTTP 401)"
            clean_msg = err.split("HTTP 401:")[-1].strip() if "HTTP 401:" in err else err.replace("HTTP 401", "").replace("401", "").replace("Unauthorized", "").strip(" :-\n\r()")
            return f"Authentication failed (HTTP 401): {clean_msg}" if clean_msg and len(clean_msg) < 80 else "Authentication failed: HTTP 401 Unauthorized"
        if "403" in err or "Forbidden" in err:
            clean_msg = err.split("HTTP 403:")[-1].strip() if "HTTP 403:" in err else err.replace("HTTP 403", "").replace("403", "").replace("Forbidden", "").strip(" :-\n\r()")
            return f"Access forbidden (HTTP 403): {clean_msg}" if clean_msg and len(clean_msg) < 80 else "Provider rejected request: HTTP 403 Forbidden"
        if "HTTP 404" in err or "404 Not Found" in err:
            return "Provider endpoint not found: HTTP 404 Not Found"
        if "timed out" in err.lower() or "timeout" in err.lower():
            return "Connection timed out. Check endpoint or network."
        if "connection refused" in err.lower() or "failed to establish" in err.lower():
            return "Connection refused. Ensure provider server is running."

        first_line = err.split("\n")[0].strip()
        if len(first_line) > 90:
            first_line = first_line[:87] + "..."
        return first_line

    def _begin_validation(self) -> None:
        """Trigger validation and model discovery with request ID."""
        self.generation += 1
        pid = (self.selected_provider or {}).get("id", "custom")
        self.active_request_id = f"req_{pid}_{self.generation}"
        self.stage = WizardStage.VALIDATING
        if self.on_validate:
            ep = self.endpoint_input or (self.selected_provider or {}).get("default_endpoint", "")
            try:
                self.on_validate(
                    provider=self.selected_provider,
                    credential=self.credential_input,
                    endpoint=ep,
                    request_id=self.active_request_id,
                )
            except TypeError:
                try:
                    self.on_validate(
                        provider=self.selected_provider,
                        credential=self.credential_input,
                        endpoint=ep,
                    )
                except Exception as e:
                    self.validation_error = self._format_error(str(e))
                    self.stage = WizardStage.ERROR
            except Exception as e:
                self.validation_error = self._format_error(str(e))
                self.stage = WizardStage.ERROR

    def complete_validation(self, success: bool, error: Optional[str] = None, request_id: Optional[str] = None) -> None:
        """Called after validation completes. Discards stale request IDs."""
        if request_id is not None and request_id != self.active_request_id:
            # Stale event: discard safely
            return

        if success:
            self.stage = WizardStage.DISCOVERING
            if self.on_discover:
                ep = self.endpoint_input or (self.selected_provider or {}).get("default_endpoint", "")
                try:
                    self.on_discover(
                        provider=self.selected_provider,
                        credential=self.credential_input,
                        endpoint=ep,
                        request_id=self.active_request_id,
                    )
                except TypeError:
                    try:
                        self.on_discover(
                            provider=self.selected_provider,
                            credential=self.credential_input,
                            endpoint=ep,
                        )
                    except Exception as e:
                        self.validation_error = self._format_error(str(e))
                        self.stage = WizardStage.ERROR
                except Exception as e:
                    self.validation_error = self._format_error(str(e))
                    self.stage = WizardStage.ERROR
        else:
            self.validation_error = self._format_error(error or "Connection validation failed.")
            self.stage = WizardStage.ERROR

    def complete_discovery(self, models: List[Dict[str, Any]], error: Optional[str] = None, request_id: Optional[str] = None) -> None:
        """Called after model discovery completes. Discards stale request IDs."""
        if request_id is not None and request_id != self.active_request_id:
            # Stale event: discard safely
            return

        if models:
            self.discovered_models = models
            self.model_selected_index = 0
            self.model_viewport_offset = 0
            self.stage = WizardStage.MODEL_SELECT
        elif error:
            self.validation_error = self._format_error(f"Model discovery failed: {error}")
            self.stage = WizardStage.ERROR
        else:
            self.discovered_models = []
            self.validation_error = "No models discovered. Check provider configuration."
            self.stage = WizardStage.ERROR

    def _handle_model_select(self, key: str) -> bool:
        if not self.discovered_models:
            return True
        if key in ("up", "k"):
            self.model_selected_index = max(0, self.model_selected_index - 1)
            return True
        elif key in ("down", "j"):
            self.model_selected_index = min(len(self.discovered_models) - 1, self.model_selected_index + 1)
            return True
        elif key in ("pageup",):
            self.model_selected_index = max(0, self.model_selected_index - self.viewport_height)
            return True
        elif key in ("pagedown",):
            self.model_selected_index = min(len(self.discovered_models) - 1, self.model_selected_index + self.viewport_height)
            return True
        elif key in ("home",):
            self.model_selected_index = 0
            return True
        elif key in ("end",):
            self.model_selected_index = len(self.discovered_models) - 1
            return True
        elif key in ("enter", "return"):
            self.selected_model = self.discovered_models[self.model_selected_index]
            self.stage = WizardStage.CAPABILITY_VIEW
            return True
        elif key in ("escape", "esc"):
            self.stage = WizardStage.CREDENTIAL_ENTRY
            return True
        return True

    def _handle_skill_select(self, key: str) -> bool:
        if key in ("up", "k"):
            self.skill_selected_index = max(0, self.skill_selected_index - 1)
            return True
        elif key in ("down", "j"):
            self.skill_selected_index = min(len(self.available_skills) - 1, self.skill_selected_index + 1)
            return True
        elif key in ("enter", "return", " "):
            skill = self.available_skills[self.skill_selected_index]
            skill["enabled"] = not skill["enabled"]
            return True
        elif key == "tab":
            # Move to summary
            self.stage = WizardStage.SUMMARY
            return True
        elif key in ("escape", "esc"):
            self.stage = WizardStage.CAPABILITY_VIEW
            return True
        return True

    def _handle_summary(self, key: str) -> bool:
        if key in ("enter", "return"):
            self.stage = WizardStage.SAVING
            if self.on_save:
                try:
                    self.on_save(
                        provider=self.selected_provider,
                        credential=self.credential_input,
                        endpoint=self.endpoint_input,
                        model=self.selected_model,
                        skills=[s for s in self.available_skills if s.get("enabled")],
                    )
                except Exception as e:
                    self.validation_error = self._format_error(f"Save failed: {e}")
                    self.stage = WizardStage.ERROR
            return True
        elif key in ("escape", "esc"):
            self.stage = WizardStage.SKILL_SELECT
            return True
        return True

    def complete_save(self, profile_id: Optional[str] = None, error: Optional[str] = None) -> None:
        """Called by the application after save completes."""
        if error:
            self.validation_error = self._format_error(error)
            self.stage = WizardStage.ERROR
        else:
            self.saved_profile_id = profile_id
            self.stage = WizardStage.COMPLETE

    # ── Rendering ───────────────────────────────────────────────────────────

    def render(self, width: int = 80) -> List[str]:
        """Render the current wizard stage."""
        if self.stage == WizardStage.PROVIDER_SELECT:
            return self._render_provider_select(width)
        elif self.stage == WizardStage.CREDENTIAL_ENTRY:
            return self._render_credential_entry(width)
        elif self.stage == WizardStage.VALIDATING:
            return self._render_status("Checking connection...", width)
        elif self.stage == WizardStage.DISCOVERING:
            return self._render_status("Discovering models...", width)
        elif self.stage == WizardStage.MODEL_SELECT:
            return self._render_model_select(width)
        elif self.stage == WizardStage.CAPABILITY_VIEW:
            return self._render_capability_view(width)
        elif self.stage == WizardStage.SKILL_SELECT:
            return self._render_skill_select(width)
        elif self.stage == WizardStage.SUMMARY:
            return self._render_summary(width)
        elif self.stage == WizardStage.SAVING:
            return self._render_status("Saving configuration...", width)
        elif self.stage == WizardStage.ERROR:
            return self._render_error(width)
        return []

    def _render_provider_select(self, width: int) -> List[str]:
        geo = WizardCardGeometry(width)
        lines = [
            geo.top_border("Setup Wizard — Provider Selection"),
            geo.row("Select your model provider:"),
            geo.empty_row(),
        ]

        for idx, item in enumerate(self._provider_list):
            if item.get("type") == "header":
                lines.append(geo.row(f"  ── {item['label']} ──"))
            else:
                marker = "▶ " if idx == self.selected_index else "  "
                name = item.get("name", item.get("id", ""))
                desc = item.get("description", "")
                line_text = f"{marker}{name}"
                if len(line_text) < geo.inner_width - 2 and desc:
                    line_text = f"{line_text} — {desc}"
                lines.append(geo.row(line_text))

        lines.append(geo.empty_row())
        lines.append(geo.row("↑/↓ select   Enter choose   Esc cancel"))
        lines.append(geo.bottom_border())
        return lines

    def _render_credential_entry(self, width: int) -> List[str]:
        geo = WizardCardGeometry(width)
        prov = self.selected_provider or {}
        prov_name = prov.get("name", "Provider")
        requires_key = prov.get("requires_api_key", False)

        lines = [
            geo.top_border(f"Setup Wizard — Configure {prov_name}"),
        ]

        if requires_key:
            cred_label = "API Key:"
            cred_display = "•" * len(self.credential_input) if self.credential_input else "(enter key)"
            marker_c = "▶ " if self._active_field == "credential" else "  "
            lines.append(geo.row(f"{marker_c}{cred_label:<12} {cred_display}"))
        else:
            lines.append(geo.row("  (no API key required)"))

        ep_label = "Endpoint:"
        marker_e = "▶ " if self._active_field == "endpoint" else "  "
        ep_display = self.endpoint_input or "(default)"
        lines.append(geo.row(f"{marker_e}{ep_label:<12} {ep_display}"))

        lines.append(geo.empty_row())
        lines.append(geo.row("Tab switch field   Enter validate   Ctrl+V paste   Esc back"))
        lines.append(geo.bottom_border())
        return lines

    def _render_model_select(self, width: int) -> List[str]:
        geo = WizardCardGeometry(width)
        lines = [
            geo.top_border("Setup Wizard — Select Model"),
            geo.row("Available models:"),
        ]

        total = len(self.discovered_models)
        vh = min(self.viewport_height, total)
        if self.model_selected_index < self.model_viewport_offset:
            self.model_viewport_offset = self.model_selected_index
        elif self.model_selected_index >= self.model_viewport_offset + vh:
            self.model_viewport_offset = self.model_selected_index - vh + 1

        visible = self.discovered_models[self.model_viewport_offset:self.model_viewport_offset + vh]

        for i, mdl in enumerate(visible):
            actual_idx = self.model_viewport_offset + i
            marker = "▶ " if actual_idx == self.model_selected_index else "  "
            mid = mdl.get("id", "unknown")
            caps = mdl.get("capabilities", [])

            cap_badges = ""
            if "tool_calling" in caps:
                cap_badges += " tools ✓"
            if "streaming" in caps:
                cap_badges += " stream ✓"
            if "vision" in caps:
                cap_badges += " vision ✓"

            lines.append(geo.row(f"{marker}{mid}"))
            if cap_badges:
                lines.append(geo.row(f"    {cap_badges.strip()}"))

        if total > vh:
            scroll_info = f"  ({self.model_viewport_offset + 1}-{min(self.model_viewport_offset + vh, total)} of {total})"
            lines.append(geo.row(scroll_info))

        lines.append(geo.empty_row())
        lines.append(geo.row("↑/↓ select   PgUp/PgDn scroll   Enter choose   Esc back"))
        lines.append(geo.bottom_border())
        return lines

    def _render_capability_view(self, width: int) -> List[str]:
        geo = WizardCardGeometry(width)
        mdl = self.selected_model or {}
        mid = mdl.get("id", "unknown")
        caps = mdl.get("capabilities", [])
        ctx = mdl.get("context_capacity")

        lines = [
            geo.top_border(f"Model Capabilities — {mid}"),
        ]

        cap_labels = {
            "text": ("Text Generation", "✓"),
            "tool_calling": ("Tool Calling", "✓"),
            "streaming": ("Streaming", "✓"),
            "vision": ("Vision", "✓"),
            "reasoning": ("Reasoning", "✓"),
            "structured_output": ("Structured Output", "✓"),
        }

        for cap_id, (label, icon) in cap_labels.items():
            status = f" {icon}" if cap_id in caps else " —"
            lines.append(geo.row(f"  {label:<24}{status}"))

        if ctx:
            lines.append(geo.row(f"  {'Context Window':<24}{ctx}"))

        lines.append(geo.empty_row())
        lines.append(geo.row("Enter continue   Esc back"))
        lines.append(geo.bottom_border())
        return lines

    def _render_skill_select(self, width: int) -> List[str]:
        geo = WizardCardGeometry(width)
        lines = [
            geo.top_border("Setup Wizard — Skills"),
            geo.row("Select optional skills:"),
            geo.empty_row(),
        ]

        for idx, skill in enumerate(self.available_skills):
            marker = "▶ " if idx == self.skill_selected_index else "  "
            check = "[✓]" if skill.get("enabled") else "[ ]"
            name = skill.get("name", "")
            lines.append(geo.row(f"{marker}{check} {name}"))

        lines.append(geo.empty_row())
        lines.append(geo.row("↑/↓ select   Enter/Space toggle   Tab continue   Esc back"))
        lines.append(geo.bottom_border())
        return lines

    def _render_summary(self, width: int) -> List[str]:
        geo = WizardCardGeometry(width)
        prov = self.selected_provider or {}
        mdl = self.selected_model or {}
        prov_name = prov.get("name", "Unknown")
        endpoint = self.endpoint_input or prov.get("default_endpoint", "")
        model_id = mdl.get("id", "not selected")
        has_cred = "Configured" if self.credential_input else "None"
        skills = [s["name"] for s in self.available_skills if s.get("enabled")]
        skills_str = ", ".join(skills) if skills else "None"

        lines = [
            geo.top_border("Configuration Summary"),
            geo.row(f"  {'Provider:':<16} {prov_name}"),
            geo.row(f"  {'Endpoint:':<16} {endpoint}"),
            geo.row(f"  {'Credential:':<16} {has_cred}"),
            geo.row(f"  {'Model:':<16} {model_id}"),
            geo.row(f"  {'Skills:':<16} {skills_str}"),
            geo.empty_row(),
            geo.row("Enter save & launch   Esc back"),
            geo.bottom_border(),
        ]
        return lines

    def _render_status(self, message: str, width: int) -> List[str]:
        geo = WizardCardGeometry(width)
        return [
            geo.top_border("Setup Wizard"),
            geo.empty_row(),
            geo.row(f"  ⟳ {message}"),
            geo.empty_row(),
            geo.bottom_border(),
        ]

    def _render_error(self, width: int) -> List[str]:
        geo = WizardCardGeometry(width)
        error = self.validation_error or "Unknown error"
        lines = [
            geo.top_border("Setup Wizard — Error"),
            geo.empty_row(),
        ]
        lines.extend(geo.wrap_rows(error, prefix="  "))
        lines.append(geo.empty_row())
        lines.append(geo.row("Enter retry   Esc back"))
        lines.append(geo.bottom_border())
        return lines

