import httpx
from botspot.utils import send_safe
from datetime import datetime
from loguru import logger

from app.app import App
from app.router import get_api_url

app = App()


async def _get_state_transitions(only_not_alerted: bool = True) -> list:
    """Get state transitions from API"""
    api_url = get_api_url()
    logger.info(f"Checking state transitions at {api_url}")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{api_url}/services/history",
            params={"only_not_alerted": only_not_alerted}
        )
        response.raise_for_status()
        return response.json()


async def _get_services() -> dict:
    """Get all services from API"""
    api_url = get_api_url()
    logger.info(f"Getting services from {api_url}")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{api_url}/services")
        response.raise_for_status()
        return response.json()


async def check_services_and_alert():
    """Check for new state transitions and send alerts"""
    try:
        # Get new state transitions
        transitions = await _get_state_transitions(only_not_alerted=True)
        if not transitions:
            return
        
        # Group transitions by service
        service_transitions = {}
        for transition in transitions:
            service_key = transition["service_key"]
            if service_key not in service_transitions:
                service_transitions[service_key] = []
            service_transitions[service_key].append(transition)
        
        # Send alerts for each service
        for service_key, transitions in service_transitions.items():
            # Format message
            lines = [f"🚨 *Service Status Change: {service_key}*\n"]
            
            for transition in transitions:
                from_state = transition["from_state"]
                to_state = transition["to_state"]
                timestamp = datetime.fromisoformat(transition["timestamp"])
                alert_message = transition.get("alert_message")
                
                lines.append(
                    f"Status changed from *{from_state}* to *{to_state}* "
                    f"at {timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
                )
                if alert_message:
                    lines.append(f"ℹ️ {alert_message}")
            
            # Send alert
            await send_safe(
                app.config.telegram_chat_id,
                "\n".join(lines),
                parse_mode="Markdown"
            )
            
            # Mark transitions as alerted
            async with httpx.AsyncClient() as client:
                for transition in transitions:
                    await client.post(
                        f"{get_api_url()}/services/history/{transition['_id']}/mark-alerted"
                    )
            
    except Exception as e:
        error_msg = f"Failed to check services: {e}"
        logger.error(error_msg)
        await send_safe(app.config.telegram_chat_id, f"❌ {error_msg}")


async def daily_services_summary():
    """Send daily summary of all services status"""
    try:
        services = await _get_services()
        if not services:
            return
        
        # Get current time for the report header
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Format full status report
        lines = [f"📊 *Daily Services Status Summary ({now})*\n"]
        
        # Group services by status
        by_status = {"alive": [], "down": [], "dead": []}
        for key, service in services.items():
            status = service["status"].lower()
            by_status[status].append((key, service))
        
        # Add alive services
        if by_status["alive"]:
            lines.append("✅ *Healthy Services:*")
            for key, service in sorted(by_status["alive"]):
                lines.append(f"- {key}")
            lines.append("")
        
        # Add troubled services with details
        troubled = by_status["down"] + by_status["dead"]
        if troubled:
            lines.append("⚠️ *Services Needing Attention:*")
            for key, service in sorted(troubled):
                status = service["status"]
                updated_at = datetime.fromisoformat(service["updated_at"])
                lines.append(
                    f"- {key}: *{status}*\n"
                    f"  Last seen: {updated_at.strftime('%Y-%m-%d %H:%M:%S')}"
                )
        
        # Send summary to configured chat
        await send_safe(
            app.config.telegram_chat_id,
            "\n".join(lines),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        error_msg = f"Failed to generate daily summary: {e}"
        logger.error(error_msg)
        await send_safe(app.config.telegram_chat_id, f"❌ {error_msg}") 