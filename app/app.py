from botspot.utils.deps_getters import get_scheduler
from loguru import logger
from pydantic import SecretStr
from pydantic_settings import BaseSettings


class AppConfig(BaseSettings):
    """Basic app configuration"""

    telegram_bot_token: SecretStr
    telegram_chat_id: int
    
    # Service Registry settings
    service_registry_url: str = "http://localhost:8765"
    check_interval_seconds: int = 15 * 60
    daily_summary_time: str = "09:00"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class App:
    name = "Service Registry Bot"

    def __init__(self, **kwargs):
        self.config = AppConfig(**kwargs)
        self.scheduler = None  # Will be set up during startup

    async def setup_scheduled_tasks(self):
        """Set up scheduled tasks for service monitoring"""
        self.scheduler = get_scheduler()
        from app.scheduled_tasks import check_services_and_alert, daily_services_summary
        
        # Check services periodically
        self.scheduler.add_job(
            check_services_and_alert,
            'interval',
            seconds=self.config.check_interval_seconds,
            id='check_services_status'
        )
        
        # Parse daily summary time
        hour, minute = map(int, self.config.daily_summary_time.split(":"))
        
        # Daily summary at configured time
        self.scheduler.add_job(
            daily_services_summary,
            'cron',
            hour=hour,
            minute=minute,
            id='daily_services_summary'
        )
        
        logger.info(
            f"Scheduled tasks set up:\n"
            f"- Status check every {self.config.check_interval_seconds // 60} minutes {self.config.check_interval_seconds % 60} seconds\n"
            f"- Daily summary at {self.config.daily_summary_time}"
        )
