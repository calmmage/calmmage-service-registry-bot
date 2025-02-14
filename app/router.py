"""Main router for the service registry bot."""

from aiogram import Router, html
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from botspot.components import bot_commands_menu
from botspot.utils import send_safe

from app.app import App
from app.routers import status, settings

router = Router()
app = App()

# Include sub-routers
router.include_router(status.router)
router.include_router(settings.router)


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
        "\nStatus Commands:\n"
        "/status - Quick status check (grouped by status and service group)\n"
        "/status_full - Detailed status with all services and groups\n"
        "/history <service_key> [limit] - View service state transition history\n"
        "\nSettings Commands:\n"
        "/settings <service_key> - Show service settings\n"
        "/toggle_alerts <service_key> - Enable/disable alerts\n"
        "/set_service_name <service_key> <name> - Set service display name\n"
        "\nOther Commands:\n"
        "/help_botspot - Show Botspot help\n"
        "/timezone - Set your timezone\n"
        "/error_test - Test error handling",
    )


@router.startup()
async def on_startup():
    """Setup scheduled tasks on startup"""
    await app.setup_scheduled_tasks()
