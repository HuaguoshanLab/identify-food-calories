"""Start Uvicorn without its raw access/exception handlers."""

import argparse
import uvicorn

from app.core.config import get_settings
from app.core.logging import configure_logging


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    arguments = parser.parse_args()
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    uvicorn.run(
        "app.main:app",
        host=arguments.host,
        port=arguments.port,
        reload=arguments.reload,
        log_config=None,
        access_log=False,
    )


if __name__ == "__main__":
    main()
