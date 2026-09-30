"""Interactive Provider -> Model Selector Overlay conforming to CC-PRD-011 and CC-ADR-007."""
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from .canvas import visible_length, visible_slice
from clairecoder.gateway.config import (
    PROVIDER_REGISTRY, ProviderCategory, ProviderProfile,
)


class ModelSelectorStage(str, Enum):
    PROVIDER_LIST = "provider_list"
    MODEL_LIST = "model_list"
    UNCONFIGURED_PROMPT = "unconfigured_prompt"


class ModelSelectorOverlay:
    """Two-level Provider → Model interactive selector overlay card."""

    def __init__(
        self,
        config_manager: Optional[Any] = None,
        active_provider_id: str = "",
        active_model_id: str = "",
    ) -> None:
        self.config_manager = config_manager
        self.stage: ModelSelectorStage = ModelSelectorStage.PROVIDER_LIST
        self.active_provider_id = active_provider_id
        self.active_model_id = active_model_id

        # Item selections
        self.providers: List[Dict[str, Any]] = []
        self.selected_provider_index: int = 0
        self.provider_viewport_offset: int = 0

        self.models: List[Dict[str, Any]] = []
        self.selected_model_index: int = 0
        self.model_viewport_offset: int = 0

        self.viewport_height: int = 8
        self.target_provider: Optional[Dict[str, Any]] = None

        # Callbacks
        self.on_select_model: Optional[Callable[[str, str], None]] = None
        self.on_configure_provider: Optional[Callable[[Dict[str, Any]], None]] = None
        self.on_close: Optional[Callable[[], None]] = None

        self.refresh()

    def refresh(self) -> None:
        """Refresh provider states from configuration manager and registry."""
        configured_profiles: Dict[str, ProviderProfile] = {}
        if self.config_manager:
            try:
                for p in self.config_manager.list_provider_profiles():
                    configured_profiles[p.id] = p
                active = self.config_manager.get_active()
                self.active_provider_id = active.get("provider_profile_id", self.active_provider_id)
                self.active_model_id = active.get("model_id", self.active_model_id)
            except Exception:
                pass

        # Build list of providers with status
        prov_list: List[Dict[str, Any]] = []
        for pid, reg in PROVIDER_REGISTRY.items():
            name = reg.get("name", pid.title())
            is_active = (pid == self.active_provider_id)
            is_configured = (pid in configured_profiles and configured_profiles[pid].enabled)
            prof = configured_profiles.get(pid)

            if is_active:
                status = "[ACTIVE]"
            elif is_configured:
                status = "[CONFIGURED]"
            elif prof and not prof.enabled:
                status = "[INCOMPLETE]"
            else:
                status = "[NOT CONFIGURED]"

            prov_list.append({
                "id": pid,
                "name": name,
                "status": status,
                "is_configured": is_configured or is_active,
                "profile": prof,
                "registry": reg,
            })

        self.providers = prov_list
        # Pre-select active provider if found
        if self.active_provider_id:
            for idx, p in enumerate(self.providers):
                if p["id"] == self.active_provider_id:
                    self.selected_provider_index = idx
                    break
        elif self.selected_provider_index >= len(self.providers):
            self.selected_provider_index = 0

    def handle_key(self, key: str) -> bool:
        """Handle keyboard navigation inside the model selector overlay."""
        clean = key.strip().lower() if key else ""

        if self.stage == ModelSelectorStage.PROVIDER_LIST:
            return self._handle_provider_key(clean)
        elif self.stage == ModelSelectorStage.MODEL_LIST:
            return self._handle_model_key(clean)
        elif self.stage == ModelSelectorStage.UNCONFIGURED_PROMPT:
            return self._handle_unconfigured_key(clean)
        return False

    def _handle_provider_key(self, key: str) -> bool:
        if not self.providers:
            if key in ("escape", "esc", "q", "back"):
                if self.on_close:
                    self.on_close()
                return True
            return True

        if key in ("up", "k"):
            self.selected_provider_index = max(0, self.selected_provider_index - 1)
            return True
        elif key in ("down", "j"):
            self.selected_provider_index = min(len(self.providers) - 1, self.selected_provider_index + 1)
            return True
        elif key == "pageup":
            self.selected_provider_index = max(0, self.selected_provider_index - self.viewport_height)
            return True
        elif key == "pagedown":
            self.selected_provider_index = min(len(self.providers) - 1, self.selected_provider_index + self.viewport_height)
            return True
        elif key == "home":
            self.selected_provider_index = 0
            return True
        elif key == "end":
            self.selected_provider_index = len(self.providers) - 1
            return True
        elif key in ("enter", "return"):
            prov = self.providers[self.selected_provider_index]
            self.target_provider = prov
            if prov["is_configured"]:
                # Load models from profile
                prof: Optional[ProviderProfile] = prov.get("profile")
                models = []
                if prof and prof.available_models:
                    for mid in prof.available_models:
                        is_active_m = (prov["id"] == self.active_provider_id and mid == self.active_model_id)
                        models.append({
                            "id": mid,
                            "is_active": is_active_m,
                        })
                self.models = models
                self.selected_model_index = 0
                self.stage = ModelSelectorStage.MODEL_LIST
            else:
                self.stage = ModelSelectorStage.UNCONFIGURED_PROMPT
            return True
        elif key in ("escape", "esc", "q", "back"):
            if self.on_close:
                self.on_close()
            return True
        return True

    def _handle_model_key(self, key: str) -> bool:
        if not self.models:
            if key in ("escape", "esc", "q", "back"):
                self.stage = ModelSelectorStage.PROVIDER_LIST
                return True
            return True

        if key in ("up", "k"):
            self.selected_model_index = max(0, self.selected_model_index - 1)
            return True
        elif key in ("down", "j"):
            self.selected_model_index = min(len(self.models) - 1, self.selected_model_index + 1)
            return True
        elif key == "pageup":
            self.selected_model_index = max(0, self.selected_model_index - self.viewport_height)
            return True
        elif key == "pagedown":
            self.selected_model_index = min(len(self.models) - 1, self.selected_model_index + self.viewport_height)
            return True
        elif key == "home":
            self.selected_model_index = 0
            return True
        elif key == "end":
            self.selected_model_index = len(self.models) - 1
            return True
        elif key in ("enter", "return"):
            selected_model = self.models[self.selected_model_index]
            if self.target_provider and self.on_select_model:
                self.on_select_model(self.target_provider["id"], selected_model["id"])
            if self.on_close:
                self.on_close()
            return True
        elif key in ("escape", "esc", "q", "back"):
            self.stage = ModelSelectorStage.PROVIDER_LIST
            return True
        return True

    def _handle_unconfigured_key(self, key: str) -> bool:
        if key in ("enter", "return"):
            # Launch setup wizard for this provider
            if self.target_provider and self.on_configure_provider:
                self.on_configure_provider(self.target_provider["registry"])
            return True
        elif key in ("escape", "esc", "q", "back"):
            self.stage = ModelSelectorStage.PROVIDER_LIST
            return True
        return True

    def render(self, width: int = 58) -> List[str]:
        """Render the model selector card matching TUI spatial design."""
        card_w = max(42, min(width, 58))
        inner_w = card_w - 4

        def frame_line(content: str = "") -> str:
            vis = visible_length(content)
            if vis > inner_w:
                content = visible_slice(content, 0, inner_w)
                vis = visible_length(content)
            pad = max(0, inner_w - vis)
            return f"│ {content}{' ' * pad} │"

        lines: List[str] = []

        if self.stage == ModelSelectorStage.PROVIDER_LIST:
            top_bar = "╭─ Select Provider " + ("─" * max(0, card_w - 23)) + " x ─╮"
            lines.append(top_bar)
            lines.append(frame_line(""))

            start = max(0, min(self.selected_provider_index - self.viewport_height + 1, len(self.providers) - self.viewport_height)) if len(self.providers) > self.viewport_height else 0
            visible_provs = self.providers[start : start + self.viewport_height]

            for idx, prov in enumerate(visible_provs):
                real_idx = start + idx
                is_sel = (real_idx == self.selected_provider_index)
                pointer = "▶ " if is_sel else "  "
                p_name = prov["name"]
                p_status = prov["status"]
                
                # Format line with name on left, badge on right
                avail_name_w = max(10, inner_w - len(p_status) - 4)
                if visible_length(p_name) > avail_name_w:
                    p_name = visible_slice(p_name, 0, avail_name_w - 2) + ".."
                pad_space = max(1, inner_w - 2 - visible_length(p_name) - len(p_status))
                row = f"{pointer}{p_name}{' ' * pad_space}{p_status}"
                lines.append(frame_line(row))

            while len(lines) < self.viewport_height + 2:
                lines.append(frame_line(""))

            lines.append(frame_line(""))
            lines.append(frame_line("↑/↓ select   Enter choose   Esc back"))
            lines.append("╰" + ("─" * (card_w - 2)) + "╯")

        elif self.stage == ModelSelectorStage.MODEL_LIST:
            prov_name = self.target_provider["name"] if self.target_provider else "Provider"
            title = f"╭─ {prov_name} Models "
            top_bar = title + ("─" * max(0, card_w - visible_length(title) - 4)) + " x ─╮"
            lines.append(top_bar)
            lines.append(frame_line(""))

            if self.models:
                start = max(0, min(self.selected_model_index - self.viewport_height + 1, len(self.models) - self.viewport_height)) if len(self.models) > self.viewport_height else 0
                visible_models = self.models[start : start + self.viewport_height]

                for idx, m in enumerate(visible_models):
                    real_idx = start + idx
                    is_sel = (real_idx == self.selected_model_index)
                    pointer = "▶ " if is_sel else "  "
                    badge = "[ACTIVE]" if m.get("is_active") else ""
                    m_id = m["id"]
                    avail_id_w = max(10, inner_w - len(badge) - 4)
                    if visible_length(m_id) > avail_id_w:
                        m_id = visible_slice(m_id, 0, avail_id_w - 2) + ".."
                    pad_space = max(1, inner_w - 2 - visible_length(m_id) - len(badge)) if badge else max(0, inner_w - 2 - visible_length(m_id))
                    row = f"{pointer}{m_id}{' ' * pad_space}{badge}" if badge else f"{pointer}{m_id}"
                    lines.append(frame_line(row))
            else:
                lines.append(frame_line("No selectable models available."))

            while len(lines) < self.viewport_height + 2:
                lines.append(frame_line(""))

            lines.append(frame_line(""))
            lines.append(frame_line("↑/↓ select   Enter switch   Esc back"))
            lines.append("╰" + ("─" * (card_w - 2)) + "╯")

        elif self.stage == ModelSelectorStage.UNCONFIGURED_PROMPT:
            prov_name = self.target_provider["name"] if self.target_provider else "Provider"
            title = f"╭─ Configure {prov_name} "
            top_bar = title + ("─" * max(0, card_w - visible_length(title) - 4)) + " x ─╮"
            lines.append(top_bar)
            lines.append(frame_line(""))
            lines.append(frame_line(f"{prov_name}"))
            lines.append(frame_line("Provider is not configured."))
            lines.append(frame_line(""))
            lines.append(frame_line(f"▶ Configure {prov_name}"))
            lines.append(frame_line("  Esc Back"))
            lines.append(frame_line(""))
            lines.append(frame_line("Enter setup   Esc back"))
            lines.append("╰" + ("─" * (card_w - 2)) + "╯")

        return lines
