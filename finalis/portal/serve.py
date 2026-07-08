"""Run the Finalis portal: python3 -m finalis.portal.serve [db_path] [port]

Seeds the demo tenant on first run. Login: owner@demo.finalis / demo1234.
"""
from __future__ import annotations

import sys

import uvicorn

from .app import create_app
from .seed import seed


def main() -> None:
    db_path = sys.argv[1] if len(sys.argv) > 1 else "finalis-dev.db"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
    app = create_app(db_path)
    print(seed(app.state.db))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
