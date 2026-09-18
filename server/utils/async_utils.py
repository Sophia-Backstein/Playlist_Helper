"""Async utilities for offloading blocking calls from the event loop."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


async def run_blocking(func: Callable[..., T], *args, **kwargs) -> T:
    """Run a synchronous blocking function in a thread-pool executor.

    This prevents long-running calls (e.g. ffmpeg subprocess, volume analysis)
    from blocking the async event loop.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
