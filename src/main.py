from __future__ import annotations

import uvicorn

HOST = "127.0.0.1"
PORT = 8080


def main() -> None:
    uvicorn.run("bootstrap.app:create_app", factory=True, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
