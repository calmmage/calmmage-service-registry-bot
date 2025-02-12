# Service Registry Bot

A Telegram bot for monitoring service health via heartbeats.

## Features

- Monitor multiple services via heartbeats
- Group services by status (Alive/Down/Unknown)
- Send alerts when services go down
- Daily status summaries
- Self-monitoring via heartbeat

## Configuration

Copy `example.env` to `.env` and configure:

```bash
# Required: Bot token from @BotFather
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Service Registry settings
SERVICE_REGISTRY_URL=http://localhost:8765
CHECK_INTERVAL_SECONDS=60
DAILY_SUMMARY_TIME=09:00
TELEGRAM_CHAT_ID=your_chat_id  # chat to receive alerts

# Bot's own heartbeat settings
CALMMAGE_SERVICE_REGISTRY_URL=http://localhost:8765
BOT_SERVICE_KEY=service-registry-bot
```

## Self-Monitoring

The bot uses `calmlib.utils.service_registry` to monitor its own health. This is implemented in `run.py`:

```python
from calmlib.utils import run_with_heartbeat
from app.bot import run_bot

def main():
    # Get service key for heartbeat
    service_key = os.getenv("BOT_SERVICE_KEY", "service-registry-bot")
    
    # Run bot with heartbeat monitoring
    run_with_heartbeat(
        run_bot(),  # This is our async main function
        service_key=service_key,
        period=60,  # Send heartbeat every minute
        debug=False
    )
```

This means:
1. The bot monitors other services
2. The bot sends its own heartbeats
3. You can monitor the bot's health just like any other service

## Usage

### Running Locally

```bash
# Install dependencies
poetry install

# Run the bot
poetry run python run.py
```

### Docker

```bash
# Build the image
docker build -t service-registry-bot .

# Run the container
docker run -d --name service-registry-bot \
    --env-file .env \
    service-registry-bot
```

## Available Commands

- `/start` - Start the bot
- `/help` - Show help message
- `/status` - Quick status check
- `/status_full` - Detailed status with all services

## Project Structure

```
.
├── app/
│   ├── _app.py          # Core app
│   ├── bot.py           # Bot setup & launcher
│   ├── router.py          
│   └── __init__.py
├── example.env         # Example environment variables
├── pyproject.toml      # Project dependencies
├── README.md
├── Dockerfile
├── docker-compose.yaml
└── run.py              # Main entry point - for docker etc.
```

## Development

1. Install pre-commit hooks:
```bash
pre-commit install
```

2. Run tests:
```bash
poetry run pytest
```

## Docker Support

Build and run with Docker:

```bash
docker-compose up --build
```

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
