from __future__ import annotations

from app.config import config


def main() -> None:
    import uvicorn

    host = str(config.app.get("local_api_host", "127.0.0.1") or "127.0.0.1")
    port = int(config.app.get("local_api_port", 18000) or 18000)
    uvicorn.run("app.api.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
