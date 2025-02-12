from aiogram import Router, html
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from botspot.components import bot_commands_menu
from botspot.utils import send_safe
import httpx
import os
from loguru import logger
from collections import defaultdict

from app._app import App

router = Router()
app = App()


def get_api_url() -> str:
    """Get API URL from environment variable or use default"""
    return os.getenv("CALMMAGE_SERVICE_REGISTRY_URL", "http://localhost:8765")


def format_service_line(service_key: str, status_data: dict) -> str:
    """Format a single service line"""
    time_since = status_data.get("time_since_last_heartbeat_readable", "never")
    return f"`{service_key:25}`  (Last seen: {time_since} ago)"


def format_services_status(services: dict) -> list[str]:
    """Format services status grouped by status"""
    # Group services by status
    by_status = defaultdict(list)
    for service_key, data in sorted(services.items()):
        by_status[data["status"]].append((service_key, data))
    
    lines = ["*Services Status:*\n"]
    
    # Order of status display
    status_order = ["down", "unknown", "dead", "alive"]
    status_emoji = {
        "down": "🔴",
        "unknown": "❓",
        "dead": "⚫️",
        "alive": "🟢"
    }
    
    # Add each status group
    for status in status_order:
        services_with_status = by_status.get(status, [])
        if services_with_status:
            # Add status header with emoji
            lines.append(f"{status_emoji[status]} *{status.title()}:*")
            # Add each service in this status
            for service_key, data in services_with_status:
                lines.append(format_service_line(service_key, data))
            lines.append("")  # Empty line between groups
    
    return lines


@bot_commands_menu.add_command("start", "Start the bot")
@router.message(CommandStart())
async def start_handler(message: Message):
    await send_safe(message.chat.id, f"Hello, {html.bold(message.from_user.full_name)}!\n"
                                     f"Welcome to {app.name}!\n"
                                     f"Use /help to see available commands."
                                     )


@bot_commands_menu.add_command("help", "Show this help message")
@router.message(Command("help"))
async def help_handler(message: Message):
    """Basic help command handler"""
    await send_safe(message.chat.id, f"This is {app.name}. Use /start to begin.\n"
                                     "Available commands:\n"
                                     "/start - Start the bot\n"
                                     "/help - Show this help message\n"
                                     "/status - Check status of all services\n"
                                     "/help_botspot - Show Botspot help\n"
                                     "/timezone - Set your timezone\n"
                                     "/error_test - Test error handling"
                                     )


@bot_commands_menu.add_command("status", "Check status of all services")
@router.message(Command("status"))
async def status_handler(message: Message):
    """Handle status command"""
    api_url = get_api_url()
    logger.info(f"Checking services status at {api_url}")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{api_url}/status")
            response.raise_for_status()
            data = response.json()
        
        services = data["services"]
        if not services:
            await send_safe(message.chat.id, "No services registered yet.")
            return
        
        # Format and send status
        lines = format_services_status(services)
        await send_safe(message.chat.id, "\n".join(lines), parse_mode="Markdown")
            
    except Exception as e:
        error_msg = f"Failed to get services status: {e}"
        logger.error(error_msg)
        await send_safe(message.chat.id, f"❌ {error_msg}")
