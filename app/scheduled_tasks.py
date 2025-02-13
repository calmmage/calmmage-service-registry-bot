import httpx
from botspot.utils import send_safe
from datetime import datetime
from loguru import logger

from app.app import App
from app.router import get_api_url

app = App()


async def _get_state_transitions(only_not_alerted: bool = True) -> dict:
    """Get state transitions from API"""
    api_url = get_api_url()
    logger.info(f"Checking state transitions at {api_url}")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{api_url}/state-transitions", json={"only_not_alerted": only_not_alerted}
        )
        response.raise_for_status()
        data = response.json()
        return data


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
            logger.debug("No new transitions to process")
            return

        logger.debug(f"Retrieved {len(transitions)} non-alerted transitions")

        message = ""
        # Send alerts for each service
        for service_key, transition in transitions.items():
            logger.debug(f"Sending alert for {service_key}")

            # Format timestamp
            last_seen = datetime.fromisoformat(transition.get("last_seen", transition["timestamp"]))
            formatted_time = last_seen.strftime("%d %b at %H:%M")

            # Format message
            emoji = "🔴" if transition["to_state"].lower() == "down" else ""
            message += (
                f"{emoji}{service_key} is {transition['to_state']} (Last seen {formatted_time})\n"
            )

            # Mark transitions as alerted
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{get_api_url()}/mark-alerted", json={"service_key": service_key}
                )

        # Send alert
        logger.debug(f"Sending message:\n{message}")
        await send_safe(app.config.telegram_chat_id, message, parse_mode="Markdown")

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
        await send_safe(app.config.telegram_chat_id, "\n".join(lines), parse_mode="Markdown")

    except Exception as e:
        error_msg = f"Failed to generate daily summary: {e}"
        logger.error(error_msg)
        await send_safe(app.config.telegram_chat_id, f"❌ {error_msg}")
