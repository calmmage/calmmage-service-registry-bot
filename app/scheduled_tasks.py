import httpx
from botspot.utils import send_safe
from datetime import datetime
from loguru import logger

from app.app import App
from app.routers.settings import get_api_url

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
    # Get new state transitions
    transitions = await _get_state_transitions(only_not_alerted=True)
    if not transitions:
        logger.debug("No new transitions to process")
        return

    logger.debug(f"Retrieved {len(transitions)} non-alerted transitions")

    # Get all services to access their display names
    services = await _get_services()

    message = ""
    # Send alerts for each service
    for service_key, transition in transitions.items():
        logger.debug(f"Sending alert for {service_key}")

        # Get display name from service record if available
        display_name = (
            services[service_key]["service"].display_name
            if service_key in services
            else service_key
        )

        # Format timestamp
        last_seen = datetime.fromisoformat(transition.get("last_seen", transition["timestamp"]))
        formatted_time = last_seen.strftime("%d %b at %H:%M")

        # Format message
        emoji = "🔴" if transition["to_state"].lower() == "down" else ""
        message += (
            f"{emoji}{display_name} is {transition['to_state']} (Last seen {formatted_time})\n"
        )

        # Mark transitions as alerted
        async with httpx.AsyncClient() as client:
            await client.post(f"{get_api_url()}/mark-alerted", json={"service_key": service_key})

    # Send alert
    logger.debug(f"Sending message:\n{message}")
    await send_safe(app.config.telegram_chat_id, message, parse_mode="Markdown")


async def daily_services_summary():
    """Send daily summary of all services status"""
    services = await _get_services()
    if not services:
        return

    # Get current time for the report header
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Format full status report
    lines = [f"📊 *Daily Services Status Summary ({now})*\n"]

    # Group services by status
    by_status = {"alive": [], "down": [], "dead": []}
    for key, service_data in services.items():
        status = service_data["status"].lower()
        by_status[status].append((key, service_data))

    # Add alive services
    if by_status["alive"]:
        lines.append("➕ *Healthy Services:*")
        for key, service_data in sorted(by_status["alive"]):
            service = service_data["service"]
            lines.append(f"- {service.display_name}")
        lines.append("")

    # Add troubled services with details
    troubled = by_status["down"] + by_status["dead"]
    if troubled:
        lines.append("⚠️ *Services Needing Attention:*")
        for key, service_data in sorted(troubled):
            service = service_data["service"]
            status = service_data["status"]
            updated_at = datetime.fromisoformat(service_data["updated_at"])
            lines.append(
                f"- {service.display_name}: *{status}*\n"
                f"  Last seen: {updated_at.strftime('%Y-%m-%d %H:%M:%S')}"
            )

    # Send summary to configured chat
    await send_safe(app.config.telegram_chat_id, "\n".join(lines), parse_mode="Markdown")
