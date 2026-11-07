"""``python -m vps [--tls] [--host H] [--port P]``"""

from __future__ import annotations

import argparse

import uvicorn

from vps.config import Settings
from vps.main import create_app


def main() -> None:  # pragma: no cover - thin CLI
    p = argparse.ArgumentParser(description="Run the Vehicle Parking System server")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=None)
    p.add_argument("--tls", action="store_true", help="serve HTTPS with TLS 1.3 only (VPS-SR-001)")
    args = p.parse_args()
    settings = Settings.from_env()
    if args.tls:
        settings.require_tls = True
        from vps.tls import serve_tls
        serve_tls(create_app(settings), args.host, args.port or 8443)
    else:
        uvicorn.run(create_app(settings), host=args.host, port=args.port or 8000)


if __name__ == "__main__":
    main()
