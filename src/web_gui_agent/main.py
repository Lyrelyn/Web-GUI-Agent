"""Process entry point; local launch is normally performed via scripts/run.ps1."""

import uvicorn

from web_gui_agent.api.server import app
from web_gui_agent.config.settings import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
