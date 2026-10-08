"""
coder_kali/ui/__init__.py - Interfaz de Usuario para Terminal (Rich TUI & Questionary Menus).
"""

from coder_kali.ui.chat_render import (
    print_banner,
    render_ai_message,
    render_user_message,
    render_execution_result,
    render_error,
    render_info,
    render_system_status,
    console,
)

__all__ = [
    "print_banner",
    "render_ai_message",
    "render_user_message",
    "render_execution_result",
    "render_error",
    "render_info",
    "render_system_status",
    "render_agent_cooperation",
    "render_background_action",
    "console",
]
