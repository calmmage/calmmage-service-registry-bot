"""Settings router for the service registry bot.

This module handles commands related to service configuration:
- Enabling/disabling alerts
- Changing service names
- Other service-specific settings
"""

import httpx
from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from botspot.components import bot_commands_menu
from botspot.components.features.ask_user_handler import ask_user_choice
from botspot.utils import send_safe
from loguru import logger
from typing import Dict

from app.app import App

router = Router()
app = App()


def get_api_url() -> str:
    """Get API URL from environment variable"""
    return app.config.service_registry_url


async def _get_service_choices() -> Dict[str, str]:
    """Get available services as choices for ask_user_choice.
    Returns a dict of {service_key: display_text}"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{get_api_url()}/services")
        response.raise_for_status()
        services = response.json()

    choices = {}
    for service_key, service in services.items():
        # Use display name if available
        display_name = service.get("metadata", {}).get("display_name", service_key)
        alerts_enabled = service.get("alerts_enabled", True)
        status = "🔔 Enabled" if alerts_enabled else "🔕 Disabled"
        choices[service_key] = f"{display_name} ({status})"

    return choices


@bot_commands_menu.add_command("toggle_alerts", "Enable/disable alerts for a service")
@router.message(Command("toggle_alerts"))
async def toggle_alerts_handler(message: Message, state: FSMContext):
    """Handle toggle alerts command.
    Usage: /toggle_alerts <service_key>"""
    try:
        # Parse service key from command
        parts = message.text.strip().split(maxsplit=1)

        # If no service key provided, ask user to choose one
        service_key = None
        if len(parts) < 2:
            choices = await _get_service_choices()
            if not choices:
                await send_safe(
                    message.chat.id, "No services registered yet.", parse_mode="Markdown"
                )
                return

            service_key = await ask_user_choice(
                message.chat.id,
                "Which service would you like to toggle alerts for?",
                choices,
                state,
                cleanup=True,
            )
            if not service_key:
                await send_safe(message.chat.id, "Operation cancelled.", parse_mode="Markdown")
                return
        else:
            service_key = parts[1].strip()

        api_url = get_api_url()

        # Get current service state
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{api_url}/services")
            response.raise_for_status()
            services = response.json()

        if service_key not in services:
            await send_safe(
                message.chat.id, f"❌ Service '{service_key}' not found.", parse_mode="Markdown"
            )
            return

        # Toggle alerts
        current_state = services[service_key]["alerts_enabled"]
        new_state = not current_state

        # Update service
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{api_url}/configure-service",
                json={"service_key": service_key, "alerts_enabled": new_state},
            )
            response.raise_for_status()

        # Get display name if available
        display_name = services[service_key].get("metadata", {}).get("display_name", service_key)

        # Send confirmation with emoji
        state_str = "enabled 🔔" if new_state else "disabled 🔕"
        await send_safe(
            message.chat.id,
            f"✅ Alerts {state_str} for service '{display_name}'",
            parse_mode="Markdown",
        )

    except Exception as e:
        error_msg = f"Failed to toggle alerts: {e}"
        logger.error(error_msg)
        await send_safe(message.chat.id, f"❌ {error_msg}")


@bot_commands_menu.add_command("set_service_name", "Set a display name for a service")
@router.message(Command("set_service_name"))
async def set_service_name_handler(message: Message):
    """Handle set service name command.
    Usage: /set_service_name <service_key> <display_name>"""
    try:
        # Parse command arguments
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            await send_safe(
                message.chat.id,
                "❌ Please specify both service key and display name.\n"
                "Usage: /set_service_name <service_key> <display_name>",
                parse_mode="Markdown",
            )
            return

        service_key = parts[1].strip()
        display_name = parts[2].strip()
        api_url = get_api_url()

        # Check if service exists
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{api_url}/services")
            response.raise_for_status()
            services = response.json()

        if service_key not in services:
            await send_safe(
                message.chat.id, f"❌ Service '{service_key}' not found.", parse_mode="Markdown"
            )
            return

        # Update service metadata with display name
        current_metadata = services[service_key].get("metadata", {})
        current_metadata["display_name"] = display_name

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{api_url}/configure-service",
                json={"service_key": service_key, "metadata": current_metadata},
            )
            response.raise_for_status()

        await send_safe(
            message.chat.id,
            f"✅ Display name for service '{service_key}' set to '{display_name}'",
            parse_mode="Markdown",
        )

    except Exception as e:
        error_msg = f"Failed to set service name: {e}"
        logger.error(error_msg)
        await send_safe(message.chat.id, f"❌ {error_msg}")


@bot_commands_menu.add_command("settings", "Show current settings for a service")
@router.message(Command("settings"))
async def settings_handler(message: Message):
    """Handle settings command.
    Usage: /settings <service_key>"""
    try:
        # Parse service key from command
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await send_safe(
                message.chat.id,
                "❌ Please specify a service key.\n" "Usage: /settings <service_key>",
                parse_mode="Markdown",
            )
            return

        service_key = parts[1].strip()
        api_url = get_api_url()

        # Get service details
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{api_url}/services")
            response.raise_for_status()
            services = response.json()

        if service_key not in services:
            await send_safe(
                message.chat.id, f"❌ Service '{service_key}' not found.", parse_mode="Markdown"
            )
            return

        service = services[service_key]
        metadata = service.get("metadata", {})

        # Format settings message
        lines = [
            f"*Settings for {service_key}:*\n",
            f"• Display Name: {metadata.get('display_name', 'Not set')}",
            f"• Alerts: {'Enabled' if service.get('alerts_enabled', True) else 'Disabled'}",
            f"• Service Type: {service.get('service_type', 'Not set')}",
            f"• Service Group: {service.get('service_group', 'Not set')}",
            f"• Expected Period: {service.get('expected_period', 'Not set')} seconds",
            f"• Dead After: {service.get('dead_after', 'Not set')} seconds",
        ]

        await send_safe(message.chat.id, "\n".join(lines), parse_mode="Markdown")

    except Exception as e:
        error_msg = f"Failed to get service settings: {e}"
        logger.error(error_msg)
        await send_safe(message.chat.id, f"❌ {error_msg}")
