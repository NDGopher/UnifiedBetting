import json
import threading
from typing import Dict, Any, Optional, Callable

from websocket import create_connection, WebSocketConnectionClosedException


class PTOWebSocketClient:
    """Minimal GraphQL-WS client for api.picktheodds.app.

    NOTE: This is a simplified transport. PTO enforces CSRF on HTTP, but the
    websocket path can be subscribed to using the 'graphql-transport-ws' subprotocol.
    This client focuses on establishing the protocol and invoking a provided callback
    with payloads so we can map into our schema.
    """

    def __init__(self, url: str = "wss://api.picktheodds.app/graphql", on_event: Optional[Callable[[Dict[str, Any]], None]] = None, token_provider: Optional[Callable[[], Optional[str]]] = None):
        self.url = url
        self.on_event = on_event
        self.token_provider = token_provider
        self.ws = None
        self.thread: Optional[threading.Thread] = None
        self.stop_flag = False

    def start(self, query: str, variables: Optional[Dict[str, Any]] = None):
        self.stop_flag = False
        self.thread = threading.Thread(target=self._run, args=(query, variables or {}), daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_flag = True
        try:
            if self.ws:
                self.ws.close()
        except Exception:
            pass

    def _send(self, obj: Dict[str, Any]):
        self.ws.send(json.dumps(obj))

    def _run(self, query: str, variables: Dict[str, Any]):
        try:
            headers = {}
            if self.token_provider:
                token = self.token_provider() or ""
                if token:
                    headers["authorization"] = f"bearer {token}"
            self.ws = create_connection(self.url, subprotocols=["graphql-transport-ws"], header=headers, enable_multithread=True)
            # Init according to graphql-transport-ws
            init_payload = {}
            if self.token_provider:
                token = self.token_provider() or ""
                if token:
                    init_payload = {"Authorization": f"bearer {token}"}
            self._send({"type": "connection_init", "payload": init_payload})
            # Basic subscription
            op_id = "1"
            self._send({
                "id": op_id,
                "type": "subscribe",
                "payload": {
                    "query": query,
                    "variables": variables
                }
            })
            while not self.stop_flag:
                try:
                    raw = self.ws.recv()
                except WebSocketConnectionClosedException:
                    break
                if not raw:
                    continue
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue
                if msg.get("type") in ("next", "data"):
                    payload = msg.get("payload") or {}
                    if self.on_event:
                        try:
                            self.on_event(payload)
                        except Exception:
                            pass
                elif msg.get("type") in ("complete", "connection_error"):
                    break
        except Exception:
            # Silent fail; higher layer can retry
            pass

