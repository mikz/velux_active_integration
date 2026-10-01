"""Synthetic VELUX HTTP API; never contacts another service or writes a device."""

import argparse
import asyncio
import ssl
import time
from collections import Counter

from aiohttp import web

USERNAME = "lab@example.invalid"
PASSWORD = "synthetic-lab-password"
HOME = "lab-home"
GATEWAY = "lab-gateway"
TOPOLOGY = [
    {"id": GATEWAY, "type": "NXG", "name": "Lab Gateway", "future_metadata": True},
    {"id": "lab-window", "type": "NXO", "velux_type": "window", "bridge": GATEWAY},
    {"id": "lab-shutter", "type": "NXO", "velux_type": "shutter", "bridge": GATEWAY},
    {"id": "lab-switch", "type": "NXS", "bridge": GATEWAY},
]


class Cloud:
    def __init__(self):
        self.state = {
            "rain": False,
            "reachable": True,
            "outage": 0,
            "omit_rain": False,
            "reject_refresh": False,
            "password": PASSWORD,
            "token_lifetime": 10800,
        }
        self.counts = Counter()
        self.requests = []
        self.access = {}
        self.refresh = set()
        self.sequence = 0

    def app(self):
        app = web.Application()
        app.router.add_post("/oauth2/token", self.token)
        app.router.add_post("/api/homesdata", self.topology)
        app.router.add_post("/api/homestatus", self.status)
        app.router.add_get("/admin/state", self.inspect)
        app.router.add_post("/admin/state", self.configure)
        return app

    async def inspect(self, request):
        return web.json_response(
            {
                "state": {k: v for k, v in self.state.items() if k != "password"},
                "counts": dict(self.counts),
                "requests": self.requests,
            }
        )

    async def configure(self, request):
        data = await request.json()
        if data.pop("invalidate_access", False):
            self.access.clear()
        if data.pop("invalidate_refresh", False):
            self.refresh.clear()
        if data.pop("reset_payloads", False):
            for key in (
                "topology_payload",
                "status_payload",
                "status_by_home",
                "topology_outage",
                "status_delay",
                "retry_after",
            ):
                self.state.pop(key, None)
        allowed = set(self.state) | {
            "topology_payload",
            "status_payload",
            "status_by_home",
            "topology_outage",
            "status_delay",
            "retry_after",
        }
        if not set(data) <= allowed:
            raise web.HTTPBadRequest()
        self.state.update(data)
        return await self.inspect(request)

    def failure(self, request, *, auth=False):
        if self.state["outage"]:
            status = self.state["outage"]
            return web.json_response(
                {"error": {"code": 26 if status in (403, 429) else 500}},
                status=status,
                headers={"Retry-After": self.state.get("retry_after", "2")},
            )
        if not auth:
            bearer = request.headers.get("Authorization", "")
            if (
                not bearer.startswith("Bearer ")
                or self.access.get(bearer[7:], 0) < time.monotonic()
            ):
                return web.json_response({"error": {"code": 3}}, status=401)
        return None

    async def token(self, request):
        self.counts["token_requests"] += 1
        data = await request.post()
        grant = data.get("grant_type")
        self.requests.append((request.path, grant))
        self.counts[grant] += 1
        failure = self.failure(request, auth=True)
        if failure is not None:
            return failure
        if (
            not data.get("client_id")
            or not data.get("client_secret")
            or data.get("app_version") != "791302006"
        ):
            return web.json_response({"error": "invalid_client"}, status=400)
        if grant == "password":
            if data.get("scope") != "velux_scopes" or data.get("user_prefix") != "velux":
                return web.json_response({"error": "invalid_scope"}, status=400)
            valid = (
                data.get("username") == USERNAME and data.get("password") == self.state["password"]
            )
        else:
            valid = (
                grant == "refresh_token"
                and not self.state["reject_refresh"]
                and data.get("refresh_token") in self.refresh
            )
        if not valid:
            return web.json_response({"error": "invalid_grant"}, status=400)
        if grant == "refresh_token":
            self.refresh.discard(data["refresh_token"])
        self.sequence += 1
        access, refresh = f"synthetic-access-{self.sequence}", f"synthetic-refresh-{self.sequence}"
        lifetime = self.state["token_lifetime"]
        self.access[access] = time.monotonic() + lifetime
        self.refresh.add(refresh)
        return web.json_response(
            {"access_token": access, "refresh_token": refresh, "expires_in": lifetime}
        )

    async def topology(self, request):
        self.counts["homesdata"] += 1
        self.requests.append((request.path, None))
        if self.state.get("topology_outage"):
            return web.json_response(
                {},
                status=self.state["topology_outage"],
                headers={"Retry-After": self.state.get("retry_after", "2")},
            )
        failure = self.failure(request)
        if failure is not None:
            return failure
        if "topology_payload" in self.state:
            return web.json_response(self.state["topology_payload"])
        return web.json_response(
            {"body": {"homes": [{"id": HOME, "name": "VELUX Lab", "modules": TOPOLOGY}]}}
        )

    async def status(self, request):
        self.counts["homestatus"] += 1
        data = await request.post()
        self.requests.append((request.path, data.get("home_id")))
        failure = self.failure(request)
        if failure is not None:
            return failure
        if self.state.get("status_delay"):
            await asyncio.sleep(self.state["status_delay"])
        if "status_payload" in self.state:
            return web.json_response(self.state["status_payload"])
        if "status_by_home" in self.state:
            return web.json_response(self.state["status_by_home"][data["home_id"]])
        if data.get("home_id") != HOME:
            raise web.HTTPBadRequest()
        gateway = {
            "id": GATEWAY,
            "reachable": self.state["reachable"],
            "future_field": "ignored",
            "wifi_strength": 44,
        }
        if not self.state["omit_rain"]:
            gateway["is_raining"] = self.state["rain"]
        return web.json_response(
            {
                "body": {
                    "home": {
                        "modules": [
                            gateway,
                            {"id": "lab-window", "current_position": 7, "reachable": True},
                            {"id": "lab-shutter", "current_position": 20, "reachable": True},
                            {
                                "id": "lab-switch",
                                "battery_percent": 82,
                                "battery_level": 3724,
                                "rf_strength": 64,
                                "reachable": True,
                            },
                        ]
                    }
                }
            }
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cert")
    parser.add_argument("--key")
    args = parser.parse_args()
    context = None
    if args.cert:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(args.cert, args.key)
    web.run_app(
        Cloud().app(),
        host="0.0.0.0",
        port=443 if context else 8099,
        ssl_context=context,
        access_log=None,
    )
