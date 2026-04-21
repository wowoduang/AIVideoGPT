from __future__ import annotations

import signal
import sys
from app.config import config


def main() -> None:
    import uvicorn
    from uvicorn.config import Config
    from uvicorn.server import Server

    host = str(config.app.get("local_api_host", "127.0.0.1") or "127.0.0.1")
    port = int(config.app.get("local_api_port", 18000) or 18000)
    
    # 使用 Server 类而不是 uvicorn.run，更好地处理信号
    config = Config("app.api.main:app", host=host, port=port, reload=False)
    server = Server(config)
    
    # 确保能正确响应 Ctrl+C
    def handle_signal(sig, frame):
        print("\n收到关闭信号，正在停止服务器...")
        server.should_exit = True
    
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    try:
        server.run()
    except KeyboardInterrupt:
        print("\n服务器已停止")
        sys.exit(0)


if __name__ == "__main__":
    main()
