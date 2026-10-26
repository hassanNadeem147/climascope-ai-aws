import asyncio
import os
import selectors
import sys

import uvicorn


def main() -> None:
    config = uvicorn.Config("app.main:app", host="127.0.0.1", port=5555)
    server = uvicorn.Server(config)
    if os.name == "nt" and sys.version_info >= (3, 12):
        asyncio.run(
            server.serve(),
            loop_factory=lambda: asyncio.SelectorEventLoop(
                selectors.SelectSelector()
            ),
        )
        return

    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    server.run()


if __name__ == "__main__":
    main()
