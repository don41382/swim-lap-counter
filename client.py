import json
import threading
import time
import websocket

class EufyClient:
    """Handles WebSocket connection and livestream buffering."""
    def __init__(self, url: str, device_serial: str, schema_version: int = 18):
        self.url = url
        self.device_serial = device_serial
        self.schema_version = schema_version
        self.ws = None

    def connect(self):
        print(f"Connecting to WebSocket at {self.url}...", end=" ")
        self.ws = websocket.create_connection(self.url)
        print("connected.")
        self._set_schema()

    def _set_schema(self):
        schema_id = "schema"
        cmd = {"messageId": schema_id, "command": "set_api_schema", "schemaVersion": self.schema_version}
        print(f"Setting API schema version {self.schema_version} (msgId={schema_id})...")
        self.ws.send(json.dumps(cmd))
        while True:
            raw = self.ws.recv()
            try:
                msg = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue
            if msg.get("type") == "result" and msg.get("messageId") == schema_id:
                if msg.get("success"):
                    print("Schema set successfully.")
                else:
                    raise RuntimeError(f"Failed to set schema: {msg}")
                break

    def start_livestream(self):
        msg_id = f"start_ls_{int(time.time()*1000)}"
        cmd = {
            "messageId": msg_id,
            "version": self.schema_version,
            "command": "device.start_livestream",
            "serialNumber": self.device_serial,
        }
        print(f"Sending start_livestream (msgId={msg_id})...")
        self.ws.send(json.dumps(cmd))
        print("Awaiting start_livestream result...")
        while True:
            raw = self.ws.recv()
            try:
                msg = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue
            if msg.get("type") == "result" and msg.get("messageId") == msg_id:
                if msg.get("success"):
                    print(f"start_livestream acknowledged (async={msg.get('result', {}).get('async')})")
                else:
                    raise RuntimeError(f"Failed to start livestream: {msg}")
                break

        print("Waiting for video data event...")
        while True:
            raw = self.ws.recv()
            msg = json.loads(raw)
            if msg.get("type") == "event" and msg.get("event", {}).get("event") == "livestream video data":
                ev = msg["event"]
                meta = ev.get("metadata", {})
                width = meta.get("videoWidth")
                height = meta.get("videoHeight")
                fps = meta.get("videoFPS") or 15
                data = bytes(ev.get("buffer", {}).get("data", []))
                return data, {"width": width, "height": height, "fps": fps}

    def listen(self, on_data):
        def _feeder():
            try:
                while True:
                    raw = self.ws.recv()
                    msg = json.loads(raw)
                    if msg.get("type") == "event" and msg.get("event", {}).get("event") == "livestream video data":
                        data = bytes(msg["event"]["buffer"].get("data", []))
                        on_data(data)
            except Exception:
                pass

        threading.Thread(target=_feeder, daemon=True).start()

    def close(self):
        if self.ws:
            self.ws.close()