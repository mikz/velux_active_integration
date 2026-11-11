"""Host-only loopback preview of a retained, verified disposable HA lab.

No Docker port is published. Each inbound connection has one fixed destination
inside the HA container, carried over docker exec stdin/stdout. Runtime containers
gain no host route or Docker socket. Stop this process after the demonstration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import select
import socketserver
import subprocess
import sys
from contextlib import suppress
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.lab import collect_route_snapshot, json_output  # noqa: E402
from tests.lab.isolation import validate_inspect, validate_routes  # noqa: E402

# Fixed target; no request bytes can select a different host, port, or container.
RELAY = """
import os, select, socket
s = socket.create_connection(('127.0.0.1', 8123), timeout=10)
s.settimeout(None)
while True:
    ready, _, _ = select.select([0, s], [], [])
    for source in ready:
        data = os.read(0, 65536) if source == 0 else s.recv(65536)
        if not data:
            raise SystemExit
        if source == 0:
            s.sendall(data)
        else:
            view = memoryview(data)
            while view:
                view = view[os.write(1, view):]
"""


def validate_preview(run_id: str) -> str:
    if not re.fullmatch(r"velux-lab-2026-9-[34]-[0-9a-f]{8}", run_id):
        raise ValueError("Expected a lab controller run ID")
    evidence = ROOT / "artifacts/lab" / run_id
    summary = json.loads((evidence / "summary.json").read_text())
    if summary.get("status") != "passed" or summary.get("cleanup") != "retained_by_request":
        raise ValueError("Only a passed, explicitly retained lab can be previewed")
    if (
        summary["artifact_sha256"]
        != hashlib.sha256((ROOT / "dist/velux_active.zip").read_bytes()).hexdigest()
    ):
        raise ValueError("Retained lab has a different package")
    original = json.loads((evidence / "inspect.json").read_text())
    expected = {
        item["Config"]["Labels"]["io.velux-active.lab.role"]: item["Id"]
        for item in original["containers"]
    }
    containers = json_output(["docker", "inspect", expected["ha"], expected["simulator"]])
    network = json_output(["docker", "network", "inspect", f"{run_id}_lab"])[0]
    staging = ROOT / ".lab/runs" / run_id
    validate_inspect(
        network,
        containers,
        expected_project=run_id,
        expected_container_ids={expected["ha"], expected["simulator"]},
        allowed_bind_mounts=(staging / "control", staging / "artifacts"),
        allowed_volume_names=tuple(f"{run_id}_{name}" for name in ("ha_config", "sim_data")),
    )
    prepared = json.loads((evidence / "prepared.json").read_text())
    for container in containers:
        role = container["Config"]["Labels"]["io.velux-active.lab.role"]
        if not container["State"]["Running"] or container["Image"] != prepared["images"][role]:
            raise ValueError("Container stopped or image changed")
        address = container["NetworkSettings"]["Networks"][f"{run_id}_lab"]["IPAddress"]
        validate_routes(
            collect_route_snapshot(container["Id"]),
            subnet=network["IPAM"]["Config"][0]["Subnet"],
            ipv4_address=address,
        )
    return expected["ha"]


class Preview(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = False


class Connection(socketserver.BaseRequestHandler):
    def handle(self):
        process = subprocess.Popen(
            ["docker", "exec", "-i", self.server.container, "python", "-u", "-c", RELAY],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )
        try:
            with suppress(BrokenPipeError, ConnectionResetError):
                while True:
                    ready, _, _ = select.select([self.request, process.stdout], [], [])
                    for source in ready:
                        data = (
                            self.request.recv(65536)
                            if source is self.request
                            else os.read(process.stdout.fileno(), 65536)
                        )
                        if not data:
                            return
                        if source is self.request:
                            view = memoryview(data)
                            while view:
                                view = view[os.write(process.stdin.fileno(), view) :]
                        else:
                            self.request.sendall(data)
        finally:
            process.terminate()
            process.wait(timeout=10)
            process.stdin.close()
            process.stdout.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    container = validate_preview(args.run_id)
    with Preview(("127.0.0.1", args.port), Connection) as server:
        server.container = container
        print(
            f"http://127.0.0.1:{server.server_address[1]}/config/integrations/integration/velux_active",
            flush=True,
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
