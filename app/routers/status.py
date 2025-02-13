"""Status router for the service registry bot.

This module handles commands related to service status:
- Basic status check
- Detailed status with all services
- Service state transition history
"""

from collections import defaultdict

import httpx
from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from botspot.components import bot_commands_menu
from botspot.components.features.ask_user_handler import ask_user_choice
from botspot.utils import send_safe
from datetime import datetime, timedelta
from loguru import logger
from typing import Dict

from app.app import App

router = Router()
app = App()


def get_api_url() -> str:
    """Get API URL from environment variable"""
    return app.config.service_registry_url


def format_service_line(service_key: str, status_data: dict, include_details: bool = False) -> str:
    """Format a single service line"""
    time_since = status_data.get("time_since_last_heartbeat_readable", "never")
    # Use display name if available
    display_name = status_data.get("metadata", {}).get("display_name", service_key)
    line = f"`{display_name:25}`  ({time_since} ago)"

    if include_details:
        count = status_data["heartbeat_count"]
        interval = status_data.get("median_interval")
        interval_str = f", interval: {interval:.1f}s" if interval else ""
        line += f"\n    Heartbeats: {count}{interval_str}"

        # Add metadata if present
        metadata = status_data.get("metadata", {})
        if metadata:
            # Skip display_name in metadata display
            metadata_display = {k: v for k, v in metadata.items() if k != "display_name"}
            if metadata_display:
                meta_str = ", ".join(f"{k}: {v}" for k, v in metadata_display.items())
                line += f"\n    Metadata: {meta_str}"

    return line


def format_transition(transition: dict) -> str:
    """Format a single state transition"""
    timestamp = datetime.fromisoformat(transition["timestamp"])
    time_ago = datetime.now() - timestamp
    if time_ago < timedelta(minutes=1):
        time_str = "just now"
    elif time_ago < timedelta(hours=1):
        minutes = int(time_ago.total_seconds() / 60)
        time_str = f"{minutes} minutes ago"
    elif time_ago < timedelta(days=1):
        hours = int(time_ago.total_seconds() / 3600)
        time_str = f"{hours} hours ago"
    else:
        days = int(time_ago.total_seconds() / 86400)
        time_str = f"{days} days ago"

    # Add emoji based on transition type
    if transition["to_state"] == "alive":
        emoji = "✅"  # Green checkmark for back online
    elif transition["to_state"] in ["down", "dead"]:
        emoji = "❌"  # Red X for down/dead
    else:
        emoji = "❓"  # Question mark for unknown

    line = f"{emoji} {transition['from_state']} → {transition['to_state']} ({time_str})"
    if transition.get("alert_message"):
        line += f"\n    {transition['alert_message']}"
    return line


def format_services_status(
    services: dict, include_dead: bool = False, include_details: bool = False
) -> list[str]:
    """Format services status grouped by status and then by service group"""
    # Group services by status and then by group
    by_status_and_group = defaultdict(lambda: defaultdict(list))
    for service_key, data in sorted(services.items()):
        status = data["status"]
        group = data.get("service_group", "Ungrouped")  # Default group for services without one
        by_status_and_group[status][group].append((service_key, data))

    lines = ["*Services Status:*\n"]

    # Order of status display
    status_order = ["down", "unknown"] + (["dead"] if include_dead else []) + ["alive"]
    status_emoji = {"down": "➖", "unknown": "❓", "dead": "⚫️", "alive": "➕"}

    # Add each status group
    for status in status_order:
        services_by_group = by_status_and_group.get(status, {})
        if services_by_group:
            # Add status header with emoji
            lines.append(f"{status_emoji[status]} *{status.title()}:*")

            # Add each group under this status
            for group, services_in_group in sorted(services_by_group.items()):
                # Add group header if there are multiple groups
                if len(services_by_group) > 1:
                    lines.append(f"  📁 *{group}:*")

                # Add each service in this group
                for service_key, data in services_in_group:
                    service_line = format_service_line(service_key, data, include_details)
                    # Indent service lines if we're showing groups
                    if len(services_by_group) > 1:
                        service_line = "    " + service_line
                    lines.append(service_line)

                # Add space between groups if there are multiple
                if len(services_by_group) > 1:
                    lines.append("")

            # Add space between status sections
            lines.append("")

    return lines


async def _get_services_status() -> dict:
    """Helper to get services status from API"""
    api_url = get_api_url()
    logger.info(f"Checking services status at {api_url}")

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{api_url}/status")
        response.raise_for_status()
        return response.json()["services"]


async def _get_service_transitions(service_key: str, limit: int = 10) -> list[dict]:
    """Helper to get service state transitions from API"""
    api_url = get_api_url()
    logger.info(f"Getting state transitions for {service_key}")

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{api_url}/state-history", params={"service_key": service_key, "limit": limit}
        )
        response.raise_for_status()
        return response.json()["transitions"]


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
        status = service.get("status", "unknown")
        choices[service_key] = f"{display_name} ({status})"

    return choices


@bot_commands_menu.add_command("history", "View service state transition history")
@router.message(Command("history"))
async def history_handler(message: Message, state: FSMContext):
    """Handle history command - shows state transitions for a service.
    Usage: /history <service_key> [limit]"""
    try:
        # Parse command arguments
        parts = message.text.strip().split()

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
                "Which service would you like to see the history for?",
                choices,
                state,
                cleanup=True,
            )
            if not service_key:
                await send_safe(message.chat.id, "Operation cancelled.", parse_mode="Markdown")
                return
        else:
            service_key = parts[1].strip()

        # Parse limit if provided
        try:
            limit = int(parts[2]) if len(parts) > 2 else 10
        except ValueError:
            await send_safe(
                message.chat.id,
                "❌ Invalid limit value. Using default (10).",
                parse_mode="Markdown",
            )
            limit = 10

        # Get service details first to check if it exists and get display name
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{get_api_url()}/services")
            response.raise_for_status()
            services = response.json()

        if service_key not in services:
            await send_safe(
                message.chat.id, f"❌ Service '{service_key}' not found.", parse_mode="Markdown"
            )
            return

        # Get display name if available
        display_name = services[service_key].get("metadata", {}).get("display_name", service_key)

        # Get state transitions
        transitions = await _get_service_transitions(service_key, limit)

        if not transitions:
            await send_safe(
                message.chat.id,
                f"No state transitions found for service '{display_name}'.",
                parse_mode="Markdown",
            )
            return

        # Format and send transitions
        lines = [f"*State History for {display_name}:*\n"]
        for transition in transitions:
            lines.append(format_transition(transition))

        await send_safe(message.chat.id, "\n".join(lines), parse_mode="Markdown")

    except Exception as e:
        error_msg = f"Failed to get service history: {e}"
        logger.error(error_msg)
        await send_safe(message.chat.id, f"❌ {error_msg}")


@bot_commands_menu.add_command("status", "Quick status check")
@router.message(Command("status"))
async def status_handler(message: Message):
    """Handle basic status command - shows only active services"""
    try:
        services = await _get_services_status()
        if not services:
            await send_safe(message.chat.id, "No services registered yet.")
            return

        # Format and send status (without dead services and details)
        lines = format_services_status(services, include_dead=False, include_details=False)
        await send_safe(message.chat.id, "\n".join(lines), parse_mode="Markdown")

    except Exception as e:
        error_msg = f"Failed to get services status: {e}"
        logger.error(error_msg)
        await send_safe(message.chat.id, f"❌ {error_msg}")


@bot_commands_menu.add_command("status_full", "Detailed status with all services")
@router.message(Command("status_full"))
async def status_full_handler(message: Message):
    """Handle full status command - shows all services with details"""
    try:
        services = await _get_services_status()
        if not services:
            await send_safe(message.chat.id, "No services registered yet.")
            return

        # Format and send status (with dead services and details)
        lines = format_services_status(services, include_dead=True, include_details=True)
        await send_safe(message.chat.id, "\n".join(lines), parse_mode="Markdown")

    except Exception as e:
        error_msg = f"Failed to get services status: {e}"
        logger.error(error_msg)
        await send_safe(message.chat.id, f"❌ {error_msg}")
