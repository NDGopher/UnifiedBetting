import asyncio
import json
import logging
from typing import List

logger = logging.getLogger(__name__)


class SSEManager:
    def __init__(self):
        self.clients: List[asyncio.Queue] = []
        self._lock = asyncio.Lock()

    async def add_client(self, queue: asyncio.Queue):
        async with self._lock:
            self.clients.append(queue)
        logger.info(f"[SSE] Client added. Total: {len(self.clients)}")

    async def remove_client(self, queue: asyncio.Queue):
        async with self._lock:
            if queue in self.clients:
                self.clients.remove(queue)
        logger.info(f"[SSE] Client removed. Total: {len(self.clients)}")

    async def broadcast(self, message: dict):
        data = json.dumps(message)
        async with self._lock:
            dead = []
            for queue in self.clients:
                try:
                    queue.put_nowait(data)
                except asyncio.QueueFull:
                    dead.append(queue)
            for q in dead:
                self.clients.remove(q)
        if self.clients or dead:
            logger.debug(f"[SSE] Broadcast '{message.get('type')}' to {len(self.clients)} clients")


sse_manager = SSEManager()
