from datetime import datetime
import httpx
from loguru import logger
from botspot.utils import send_safe

from app.app import App
from app.router import format_services_status, get_api_url


app = App()


async def _get_services_status() -> dict:
    """Helper to get services status from API"""
    api_url = get_api_url()
    logger.info(f"Checking services status at {api_url}")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{api_url}/status")
        response.raise_for_status()
        return response.json()["services"]


async def check_services_status_and_alert():
    """Check services status and send alerts for any issues"""
    try:
        services = await _get_services_status()
        if not services:
            return
        
        # Filter services that need attention (down or unknown)
        troubled_services = {
            key: data for key, data in services.items()
            if data["status"] in ["down", "unknown"]
        }
        
        if troubled_services:
            # Format message with only troubled services
            lines = ["🚨 *Alert: Services Need Attention!*\n"]
            status_lines = format_services_status(troubled_services, include_dead=False, include_details=True)
            lines.extend(status_lines)
            
            # Send alert to configured chat
            await send_safe(app.config.telegram_chat_id, "\n".join(lines), parse_mode="Markdown")
            
    except Exception as e:
        error_msg = f"Failed to check services status: {e}"
        logger.error(error_msg)
        await send_safe(app.config.telegram_chat_id, f"❌ {error_msg}")


async def daily_services_summary():
    """Send daily summary of all services status"""
    try:
        services = await _get_services_status()
        if not services:
            return
        
        # Get current time for the report header
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Format full status report
        lines = [f"📊 *Daily Services Status Summary ({now})*\n"]
        status_lines = format_services_status(services, include_dead=True, include_details=True)
        lines.extend(status_lines)
        
        # Send summary to configured chat
        await send_safe(app.config.telegram_chat_id, "\n".join(lines), parse_mode="Markdown")
        
    except Exception as e:
        error_msg = f"Failed to generate daily summary: {e}"
        logger.error(error_msg)
        await send_safe(app.config.telegram_chat_id, f"❌ {error_msg}") 