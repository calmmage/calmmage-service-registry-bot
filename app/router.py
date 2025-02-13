from collections import defaultdict

import httpx
from aiogram import Router, html
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from botspot.components import bot_commands_menu
from botspot.utils import send_safe
from loguru import logger

from app.app import App

router = Router()
app = App()


@router.startup()
async def on_startup():
    """Setup scheduled tasks on startup"""
    await app.setup_scheduled_tasks()


def get_api_url() -> str:
    """Get API URL from environment variable"""
    return app.config.service_registry_url


def format_service_line(service_key: str, status_data: dict, include_details: bool = False) -> str:
    """Format a single service line"""
    time_since = status_data.get("time_since_last_heartbeat_readable", "never")
    line = f"`{service_key:25}`  ({time_since} ago)"

    if include_details:
        count = status_data["heartbeat_count"]
        interval = status_data.get("median_interval")
        interval_str = f", interval: {interval:.1f}s" if interval else ""
        line += f"\n    Heartbeats: {count}{interval_str}"

        # Add metadata if present
        metadata = status_data.get("metadata", {})
        if metadata:
            meta_str = ", ".join(f"{k}: {v}" for k, v in metadata.items())
            line += f"\n    Metadata: {meta_str}"

    return line


def format_services_status(
    services: dict, include_dead: bool = False, include_details: bool = False
) -> list[str]:
    """Format services status grouped by status"""
    # Group services by status
    by_status = defaultdict(list)
    for service_key, data in sorted(services.items()):
        by_status[data["status"]].append((service_key, data))

    lines = ["*Services Status:*\n"]

    # Order of status display
    status_order = ["down", "unknown"] + (["dead"] if include_dead else []) + ["alive"]
    status_emoji = {"down": "➖", "unknown": "❓", "dead": "⚫️", "alive": "➕"}

    # Add each status group
    for status in status_order:
        services_with_status = by_status.get(status, [])
        if services_with_status:
            # Add status header with emoji
            lines.append(f"{status_emoji[status]} *{status.title()}:*")
            # Add each service in this status
            for service_key, data in services_with_status:
                lines.append(format_service_line(service_key, data, include_details))
            lines.append("")  # Empty line between groups

    return lines


@bot_commands_menu.add_command("start", "Start the bot")
@router.message(CommandStart())
async def start_handler(message: Message):
    await send_safe(
        message.chat.id,
        f"Hello, {html.bold(message.from_user.full_name)}!\n"
        f"Welcome to {app.name}!\n"
        f"Use /help to see available commands.",
    )


@bot_commands_menu.add_command("help", "Show this help message")
@router.message(Command("help"))
async def help_handler(message: Message):
    """Basic help command handler"""
    await send_safe(
        message.chat.id,
        f"This is {app.name}. Use /start to begin.\n"
        "Available commands:\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/status - Quick status check\n"
        "/status_full - Detailed status with all services\n"
        "/help_botspot - Show Botspot help\n"
        "/timezone - Set your timezone\n"
        "/error_test - Test error handling",
    )


async def _get_services_status() -> dict:
    """Helper to get services status from API"""
    api_url = get_api_url()
    logger.info(f"Checking services status at {api_url}")

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{api_url}/status")
        response.raise_for_status()
        return response.json()["services"]


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
