def get_api_url() -> str:
    """Get API URL from environment variable"""

    from app.router import app

    return app.config.service_registry_url
