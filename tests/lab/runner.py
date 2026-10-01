"""Validate the packaged integration through real HA REST/WebSocket APIs."""

import asyncio
import hashlib
import json
import os
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path

import aiohttp

from .cloud import PASSWORD, USERNAME

ARTIFACTS = Path("/artifacts")
CONTROL = Path("/control")
RAIN = "binary_sensor.gateway_lab_gateway_is_raining"


async def eventually(function, predicate=bool, *, timeout=45):  # noqa: ASYNC109
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            last = await function()
            if predicate(last):
                return last
        except aiohttp.ClientError, ConnectionError, TimeoutError:
            pass
        await asyncio.sleep(0.25)
    raise AssertionError(f"Condition not reached within {timeout}s")


class Lab:
    def __init__(self, session):
        self.session = session
        self.base = os.environ["LAB_HA_URL"]
        self.cloud = os.environ["LAB_SIM_URL"]
        self.token = None
        self.results = []

    async def request(self, method, path, data=None):
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        async with self.session.request(
            method,
            self.base + path,
            json=data,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=180)
            if path.startswith("/api/services/lab_probe/")
            else None,
        ) as resp:
            # Never include a response body that could contain credentials in an error.
            assert resp.status < 400, f"HA {method} {path}: HTTP {resp.status}"
            return await resp.json() if resp.content_type == "application/json" else None

    async def ws(self, command, **fields):
        async with self.session.ws_connect(self.base + "/api/websocket") as ws:
            assert (await ws.receive_json())["type"] == "auth_required"
            await ws.send_json({"type": "auth", "access_token": self.token})
            assert (await ws.receive_json())["type"] == "auth_ok"
            await ws.send_json({"id": 1, "type": command, **fields})
            result = await ws.receive_json()
            assert result.get("success"), f"HA WebSocket {command} failed"
            return result.get("result")

    async def probe(self, case):
        async def registered():
            services = await self.request("GET", "/api/services")
            return any(
                item["domain"] == "lab_probe" and "run" in item["services"] for item in services
            )

        # Entry LOADED can precede independent lab component setup after restart.
        # Wait for the native service registry, then dispatch the tested call once.
        await eventually(registered, timeout=120)
        result = await self.request(
            "POST", "/api/services/lab_probe/run?return_response", {"case": case}
        )
        return result["service_response"]

    async def ws_failure(self, command, **fields):
        async with self.session.ws_connect(self.base + "/api/websocket") as ws:
            assert (await ws.receive_json())["type"] == "auth_required"
            await ws.send_json({"type": "auth", "access_token": self.token})
            assert (await ws.receive_json())["type"] == "auth_ok"
            await ws.send_json({"id": 1, "type": command, **fields})
            assert not (await ws.receive_json())["success"]

    async def sim(self, changes=None):
        async with self.session.request(
            "POST" if changes is not None else "GET", self.cloud + "/admin/state", json=changes
        ) as resp:
            assert resp.status == 200
            return await resp.json()

    async def state(self):
        return (await self.request("GET", f"/api/states/{self.rain}"))["state"]

    async def refresh(self, expected):
        await self.request("POST", "/api/services/velux_active/refresh", {})
        await eventually(self.state, lambda state: state == expected)

    async def refresh_failure(self):
        async with self.session.post(
            self.base + "/api/services/velux_active/refresh",
            json={},
            headers={"Authorization": f"Bearer {self.token}"},
        ) as response:
            assert response.status in (400, 500), "Cloud failure must fail the HA action"
        await eventually(self.state, lambda state: state == "unavailable")

    async def preferences(self):
        entities = {
            e["unique_id"]: {
                key: e.get(key) for key in ("entity_id", "name", "disabled_by", "device_id")
            }
            for e in await self.ws("config/entity_registry/list")
            if e["config_entry_id"] == self.entry
        }
        device_ids = {e["device_id"] for e in entities.values()}
        devices = {
            d["id"]: d.get("name_by_user")
            for d in await self.ws("config/device_registry/list")
            if d["id"] in device_ids
        }
        return {"entities": entities, "devices": devices}

    async def assert_live_legacy_inventory(self, fixture):
        """Original disabled preferences and every live enabled ID are required."""
        expected = {item["unique_id"]: item["entity_id"] for item in fixture["entities"]}
        assert await self.registry() == expected
        states = {state["entity_id"]: state for state in await self.request("GET", "/api/states")}
        entries = [
            e
            for e in await self.ws("config/entity_registry/list")
            if e["config_entry_id"] == self.entry
        ]
        assert len(entries) == len(expected)
        for item in fixture["entities"]:
            assert (item["entity_id"] in states) is not item["disabled"]
        assert self.rain in states

    async def loaded(self):
        entries = await self.ws("config_entries/get")
        return any(e["entry_id"] == self.entry and e["state"] == "loaded" for e in entries)

    async def restart(self):
        """Start a new HA process after virtual deadlines; never reset the gate."""
        nonce = secrets.token_hex(6)
        (CONTROL / f"request-{nonce}.json").write_text(
            json.dumps(
                {"run_id": os.environ["LAB_RUN_ID"], "action": "restart", "request_id": nonce}
            )
        )
        await eventually(
            lambda: asyncio.to_thread((CONTROL / f"ack-{nonce}.json").exists), timeout=120
        )
        await eventually(self.loaded, timeout=120)

    async def registry(self):
        return {
            e["unique_id"]: e["entity_id"]
            for e in await self.ws("config/entity_registry/list")
            if e["config_entry_id"] == self.entry
        }

    @asynccontextmanager
    async def scenario(self, name):
        record = {"name": name, "status": "running"}
        self.results.append(record)
        print(f"Starting {name}", flush=True)
        try:
            yield
        except Exception as error:
            record.update(status="failed", error=type(error).__name__)
            raise
        else:
            record["status"] = "passed"
        finally:
            (ARTIFACTS / "scenarios.json").write_text(json.dumps(self.results, indent=2) + "\n")
            print(f"{name}: {record['status']}", flush=True)

    async def run(self):
        async with self.scenario("native-onboarding-and-version"):

            async def ready():
                async with self.session.get(self.base + "/api/onboarding") as response:
                    return response.status == 200

            await eventually(ready, timeout=180)
            ha_password = secrets.token_urlsafe(24)
            user = await self.request(
                "POST",
                "/api/onboarding/users",
                {
                    "client_id": self.base + "/",
                    "name": "VELUX Lab",
                    "username": "velux_lab",
                    "password": ha_password,
                    "language": "en",
                },
            )
            async with self.session.post(
                self.base + "/auth/token",
                data={
                    "grant_type": "authorization_code",
                    "code": user["auth_code"],
                    "client_id": self.base + "/",
                },
            ) as response:
                assert response.status == 200
                tokens = await response.json()
            self.token = tokens["access_token"]
            (CONTROL / "secrets.json").write_text(
                json.dumps([ha_password, self.token, tokens["refresh_token"], PASSWORD])
            )
            (CONTROL / "preview-login.json").write_text(
                json.dumps({"username": "velux_lab", "password": ha_password})
            )
            await self.request("POST", "/api/onboarding/core_config", {})
            await self.request("POST", "/api/onboarding/analytics", {})
            await self.request(
                "POST",
                "/api/onboarding/integration",
                {"client_id": self.base + "/", "redirect_uri": self.base + "/?auth_callback=1"},
            )
            config = await self.request("GET", "/api/config")
            assert config["version"] == os.environ["LAB_HA_VERSION"]
            await eventually(self.sim)

        async with self.scenario("legacy-first-setup-preserves-live-complete-inventory"):
            fixture = json.loads(
                await asyncio.to_thread(Path("tests/fixtures/legacy_v1.json").read_text)
            )
            self.entry = fixture["entry_id"]
            await eventually(self.loaded)
            expected = {item["unique_id"]: item["entity_id"] for item in fixture["entities"]}
            self.original_ids = expected
            self.rain = expected["lab-gateway_is_raining"]
            await self.assert_live_legacy_inventory(fixture)
            self.original_preferences = await self.preferences()
            await eventually(self.state, lambda value: value == "off")
            for entity in ("cover.window_ndow", "cover.shutter_tter"):
                state = await self.request("GET", "/api/states/" + entity)
                assert state["attributes"]["supported_features"] == 0
            before = (await self.sim())["counts"].get("refresh_token", 0)
            await self.refresh("off")
            assert (await self.sim())["counts"].get("refresh_token", 0) == before
            flow = await self.request(
                "POST", "/api/config/config_entries/flow", {"handler": "velux_active"}
            )
            assert flow["type"] == "abort" and flow["reason"] == "single_instance_allowed"

        async with self.scenario("packaged-local-brand-image"):
            async with self.session.get(
                self.base + "/api/brands/integration/velux_active/icon.png",
                headers={"Authorization": f"Bearer {self.token}"},
            ) as response:
                assert response.status == 200
                assert response.content_type == "image/png"
                payload = await response.read()
            import zipfile

            with zipfile.ZipFile("/opt/velux-active/velux_active.zip") as archive:
                assert payload == archive.read("brand/icon.png")

        async with self.scenario("native-installed-member-and-client-origin-proof"):
            self.native_proof = await self.probe("proof")
            assert (
                self.native_proof["client"]["wheel_sha256"] == os.environ["LAB_CLIENT_WHEEL_SHA256"]
            )

        async with self.scenario("pre-candidate-recorder-history-and-unit-preferences"):
            self.statistics_proof = await self.probe("statistics")
            assert self.statistics_proof["prior_hourly_samples_retained"] == 3
            assert self.statistics_proof["battery_percent_positive_control"]

        async with self.scenario("native-migrated-composite-and-child-removal"):
            registry = await self.probe("registry")
            before_entities = [
                record
                for record in await self.ws("config/entity_registry/list")
                if record["entity_id"] == "sensor.other_retained"
            ]
            before_devices = [
                record
                for record in await self.ws("config/device_registry/list")
                if record["id"] == registry["other"]
            ]
            assert len(before_entities) == len(before_devices) == 1
            await self.ws_failure("config/device_registry/remove", device_id=registry["composite"])
            await self.ws("config/device_registry/remove", device_id=registry["own"])
            await self.ws("config/device_registry/remove", device_id=registry["child"])
            assert [
                record
                for record in await self.ws("config/entity_registry/list")
                if record["entity_id"] == "sensor.other_retained"
            ] == before_entities
            retained = [
                record
                for record in await self.ws("config/device_registry/list")
                if record["id"] == registry["other"]
            ]
            assert retained[0]["name_by_user"] == before_devices[0]["name_by_user"]
            assert any(
                record["id"] == registry["parent"]
                for record in await self.ws("config/device_registry/list")
            )

        async with self.scenario("rain-transitions-and-missing-measurement"):
            await self.sim({"rain": True})
            await self.refresh("on")
            await self.sim({"omit_rain": True})
            await self.refresh("unknown")
            await self.sim({"omit_rain": False, "rain": False})
            await self.refresh("off")

        async with self.scenario("strict-wire-rain-and-duplicate-status-failures"):
            for invalid in ([], {}, "", "false", 0, 1, "true"):
                await self.sim({"rain": invalid})
                await self.refresh_failure()
            for value, expected in ((None, "unknown"), (False, "off"), (True, "on")):
                await self.sim({"rain": value})
                await self.refresh(expected)
            for reverse in (False, True):
                records = [
                    {"id": "lab-gateway", "is_raining": False},
                    {"id": "lab-gateway", "is_raining": True},
                ]
                await self.sim(
                    {
                        "status_payload": {
                            "body": {"home": {"modules": records[::-1] if reverse else records}}
                        }
                    }
                )
                await self.refresh_failure()
            await self.sim({"reset_payloads": True, "rain": False})
            await self.refresh("off")

        async with self.scenario("native-entry-diagnostics-privacy"):
            async with self.session.get(
                self.base + f"/api/diagnostics/config_entry/{self.entry}",
                headers={"Authorization": f"Bearer {self.token}"},
            ) as response:
                assert response.status == 200 and response.content_type == "application/json"
                assert "Synthetic legacy account" not in response.headers.get(
                    "Content-Disposition", ""
                )
                report = await response.json()
            assert report["data"]["supported_model_counts"] == {
                "gateway": 1,
                "window": 1,
                "shutter": 1,
                "sensor": 1,
            }
            encoded = json.dumps(report["data"])
            assert all(
                value not in encoded
                for value in (USERNAME, PASSWORD, "lab-home", "lab-gateway", "VELUX Lab")
            )
            assert "home_assistant" in report and "integration_manifest" in report

        async with self.scenario("unreachable-gateway-and-recovery"):
            await self.sim({"reachable": False})
            await self.refresh("unavailable")
            await self.sim({"reachable": True})
            await self.refresh("off")

        async with self.scenario("cloud-outage-and-rate-limit"):
            before = (await self.sim())["counts"]["password"]
            for failure in (503, 429, 403):
                await self.sim({"outage": failure})
                await self.refresh_failure()
                assert (await self.sim())["counts"]["password"] == before
                await self.sim({"outage": 0})
                if failure in (429, 403):
                    # The real-time cloud Retry-After deadline must expire.
                    await asyncio.sleep(2.1)
                await self.refresh("off")

        async with self.scenario("rejected-access-token-and-refresh-rotation"):
            before = (await self.sim())["counts"].get("refresh_token", 0)
            await self.sim({"invalidate_access": True, "rain": True})
            await self.refresh("on")
            assert (await self.sim())["counts"]["refresh_token"] == before + 1
            before = (await self.sim())["counts"]["password"]
            await self.sim({"invalidate_access": True, "invalidate_refresh": True, "rain": False})
            await self.refresh("off")
            assert (await self.sim())["counts"]["password"] == before + 1

        async with self.scenario("native-reload-preserves-entity-identities"):
            await self.request("POST", f"/api/config/config_entries/entry/{self.entry}/reload", {})
            await eventually(self.loaded)
            assert await self.registry() == self.original_ids
            assert await self.preferences() == self.original_preferences
            await self.assert_live_legacy_inventory(fixture)
            await self.sim({"rain": True})
            await self.refresh("on")

        async with self.scenario("restart-preserves-credentials-and-rain-entity"):
            nonce = secrets.token_hex(6)
            (CONTROL / f"request-{nonce}.json").write_text(
                json.dumps(
                    {"run_id": os.environ["LAB_RUN_ID"], "action": "restart", "request_id": nonce}
                )
            )

            async def acknowledged():
                return (CONTROL / f"ack-{nonce}.json").exists()

            await eventually(acknowledged, timeout=120)
            await eventually(self.loaded, timeout=120)
            await eventually(self.state, lambda value: value == "on")
            assert await self.registry() == self.original_ids
            assert await self.preferences() == self.original_preferences
            await self.assert_live_legacy_inventory(fixture)

        async with self.scenario("native-reauthentication-preserves-entry"):
            new_password = "changed-synthetic-password"
            await self.sim(
                {"password": new_password, "invalidate_access": True, "invalidate_refresh": True}
            )
            await self.refresh_failure()

            async def reauth():
                return [
                    f
                    for f in await self.ws("config_entries/flow/progress")
                    if f["handler"] == "velux_active"
                ]

            flows = await eventually(reauth)
            assert len(flows) == 1
            issues = await self.ws("repairs/list_issues")
            matching = [
                issue
                for issue in issues["issues"]
                if issue["issue_id"] == f"config_entry_reauth_velux_active_{self.entry}"
            ]
            assert len(matching) == 1 and matching[0]["issue_domain"] == "velux_active"
            result = await self.request(
                "POST",
                "/api/config/config_entries/flow/" + flows[0]["flow_id"],
                {"username": USERNAME, "password": new_password},
            )
            assert result["reason"] == "reauth_successful"
            await eventually(self.loaded)
            issues = await self.ws("repairs/list_issues")
            assert all(
                issue["issue_id"] != f"config_entry_reauth_velux_active_{self.entry}"
                for issue in issues["issues"]
            )
            await eventually(self.state, lambda value: value == "on")
            assert await self.registry() == self.original_ids
            assert await self.preferences() == self.original_preferences
            await self.assert_live_legacy_inventory(fixture)
            await self.sim({"rain": False})
            await self.refresh("off")

        async with self.scenario("remove-and-fresh-native-user-flow"):
            legacy_entry = self.entry
            await self.request("DELETE", f"/api/config/config_entries/entry/{legacy_entry}")
            assert not await self.registry()
            await self.sim(
                {"password": PASSWORD, "invalidate_access": True, "invalidate_refresh": True}
            )
            flow = await self.request(
                "POST", "/api/config/config_entries/flow", {"handler": "velux_active"}
            )
            path = "/api/config/config_entries/flow/" + flow["flow_id"]
            wrong = await self.request("POST", path, {"username": USERNAME, "password": "wrong"})
            assert wrong["errors"]["base"] == "invalid_auth"
            result = await self.request("POST", path, {"username": USERNAME, "password": PASSWORD})
            assert result["type"] == "create_entry"
            self.entry = result["result"]["entry_id"]
            assert self.entry != legacy_entry
            await eventually(self.loaded)
            fresh = await self.registry()
            assert set(fresh) == set(self.original_ids)
            self.rain = fresh["lab-gateway_is_raining"]
            await eventually(self.state, lambda state: state == "off")
            await self.sim({"rain": True})
            await self.refresh("on")

        async with self.scenario("raw-homekit-router-and-native-cloud-confirmation"):
            await self.request("DELETE", f"/api/config/config_entries/entry/{self.entry}")
            await self.sim({"rain": False})
            result = await self.probe("discovery")
            assert len(result["routes"]) == 4 and result["unverified_variant_rejected"]
            self.discovery_routes = result["routes"]
            path = "/api/config/config_entries/flow/" + result["flow_id"]
            confirmation = await self.request("POST", path, {})
            assert confirmation["step_id"] == "user"
            wrong = await self.request("POST", path, {"username": USERNAME, "password": "wrong"})
            assert wrong["errors"]["base"] == "invalid_auth"
            created = await self.request("POST", path, {"username": USERNAME, "password": PASSWORD})
            assert created["type"] == "create_entry"
            self.entry = created["result"]["entry_id"]
            await eventually(self.loaded)
            self.rain = (await self.registry())["lab-gateway_is_raining"]
            await self.refresh("off")

        async with self.scenario("native-localized-entity-and-new-registration-defaults"):
            defaults = await self.probe("new-defaults")
            assert defaults["new_only_defaults_verified"]
            original_rain = self.rain
            self.rain = defaults["rain_entity_id"]
            before = await self.registry()
            records = [
                record
                for record in await self.ws("config/entity_registry/list")
                if record["config_entry_id"] == self.entry
                and record["unique_id"].startswith("never-seen-localized_")
            ]
            assert any(
                record["unique_id"].endswith("_last_seen")
                and record["disabled_by"] == "integration"
                for record in records
            )
            assert (
                next(
                    record
                    for record in records
                    if record["unique_id"] == "never-seen-localized_is_raining"
                )["disabled_by"]
                is None
            )
            await self.ws("config/core/update", language="cs")
            await self.request("POST", f"/api/config/config_entries/entry/{self.entry}/reload", {})
            await eventually(self.loaded)
            localized = await self.request("GET", "/api/states/" + self.rain)
            assert localized["attributes"]["friendly_name"] == "New Gateway Déšť"
            assert await self.registry() == before
            await self.ws("config/core/update", language="en")
            await self.request("POST", f"/api/config/config_entries/entry/{self.entry}/reload", {})
            await eventually(self.loaded)
            await self.refresh("off")
            await self.sim({"reset_payloads": True})
            await self.request("POST", f"/api/config/config_entries/entry/{self.entry}/reload", {})
            await eventually(self.loaded)
            await self.ws("config/device_registry/remove", device_id=defaults["device_id"])
            self.rain = original_rain
            await self.refresh("off")

        async with self.scenario("logical-clock-topology-and-native-stale-removal"):
            result = await self.probe("topology")
            assert len(result["checks"]) == 12
            await self.ws("config/device_registry/remove", device_id=result["dynamic_device_id"])
            assert result["dynamic_entity_id"] not in {
                state["entity_id"] for state in await self.request("GET", "/api/states")
            }
            self.logical_clock_checks = result["checks"]
            reappeared = await self.probe("reappear")
            assert reappeared["one_live_entity"] and reappeared["no_permanent_suppression"]
            self.reappearance_proof = reappeared
            await self.ws("config/device_registry/remove", device_id=reappeared["device_id"])
            # Full native restart separates virtual decisions from final real-time work.
            nonce = secrets.token_hex(6)
            (CONTROL / f"request-{nonce}.json").write_text(
                json.dumps(
                    {
                        "run_id": os.environ["LAB_RUN_ID"],
                        "action": "restart",
                        "request_id": nonce,
                    }
                )
            )
            await eventually(
                lambda: asyncio.to_thread((CONTROL / f"ack-{nonce}.json").exists), timeout=120
            )
            await eventually(self.loaded, timeout=120)
            await self.sim({"rain": False})
            await self.refresh("off")

        async with self.scenario("logical-clock-raw-multi-home-http-budgets"):
            self.budget_proof = await self.probe("budgets")
            assert self.budget_proof["global_429_no_http"]
            assert self.budget_proof["account_wide_duplicates_rejected"]
            await self.restart()
            await self.refresh("off")

        self.retry_proofs = []
        for endpoint in ("auth", "topology"):
            async with self.scenario("native-setup-retry-shared-deadline-" + endpoint):
                proof = await self.probe("retry-" + endpoint)
                assert proof["native_retry_after_six_seconds_no_http"]
                assert proof["expiry_accepts_fresh_credentials"]
                self.retry_proofs.append(proof)
                await self.restart()
                await self.refresh("off")

        async with self.scenario("zero-entity-native-polling-discovers-without-manual-refresh"):
            await self.request("DELETE", f"/api/config/config_entries/entry/{self.entry}")
            await self.sim({"topology_payload": {"body": {"homes": []}}})
            flow = await self.request(
                "POST", "/api/config/config_entries/flow", {"handler": "velux_active"}
            )
            result = await self.request(
                "POST",
                "/api/config/config_entries/flow/" + flow["flow_id"],
                {"username": USERNAME, "password": PASSWORD},
            )
            self.entry = result["result"]["entry_id"]
            await eventually(self.loaded)
            assert not await self.registry()
            self.zero_entity_proof = await self.probe("automatic")
            assert (
                self.zero_entity_proof["native_timer_discovered"]
                and self.zero_entity_proof["manual_requests"] == 0
            )
            self.rain = (await self.registry())["lab-gateway_is_raining"]
            await self.refresh("off")

        async with self.scenario("all-disabled-native-polling-discovers-without-manual-refresh"):
            records = [
                record
                for record in await self.ws("config/entity_registry/list")
                if record["config_entry_id"] == self.entry
            ]
            enabled_records = [record for record in records if record["disabled_by"] is None]
            for record in enabled_records:
                await self.ws(
                    "config/entity_registry/update",
                    entity_id=record["entity_id"],
                    disabled_by="user",
                )
            await self.request("POST", f"/api/config/config_entries/entry/{self.entry}/reload", {})
            await eventually(self.loaded)
            self.all_disabled_proof = await self.probe("automatic")
            assert (
                self.all_disabled_proof["native_timer_discovered"]
                and self.all_disabled_proof["manual_requests"] == 0
            )
            # Already disabled integration/user choices were never overwritten.
            for record in enabled_records:
                await self.ws(
                    "config/entity_registry/update",
                    entity_id=record["entity_id"],
                    disabled_by=record["disabled_by"],
                )
            await self.request("POST", f"/api/config/config_entries/entry/{self.entry}/reload", {})
            await eventually(self.loaded)
            await self.refresh("off")

        async with self.scenario("native-unload-owned-resource-and-probe-cleanup"):
            self.cleanup_proof = await self.probe("cleanup")
            assert self.cleanup_proof == {
                "candidate_listeners": 0,
                "candidate_pending_manual": 0,
                "shared_session_open": True,
                "probe_service_removed": True,
                "cancelled_waiter_did_not_cancel_shared_work": True,
                "unload_returns_action_error_to_waiter": True,
            }
            await self.refresh("off")

        (ARTIFACTS / "acceptance.json").write_text(
            json.dumps(
                {
                    "ha_version": os.environ["LAB_HA_VERSION"],
                    "source_revision": os.environ["LAB_SOURCE_REVISION"],
                    "scenarios": self.results,
                    "artifact_sha256": os.environ["LAB_ARTIFACT_SHA256"],
                    "client_wheel_sha256": os.environ["LAB_CLIENT_WHEEL_SHA256"],
                    "client_proof": json.loads(
                        await asyncio.to_thread((CONTROL / "client-proof.json").read_text)
                    ),
                    "scope": "local validation candidate; requires the matching local wheel",
                    "native_proof": self.native_proof,
                    "statistics_proof": self.statistics_proof,
                    "discovery_routes": self.discovery_routes,
                    "logical_clock_checks": self.logical_clock_checks,
                    "reappearance_proof": self.reappearance_proof,
                    "cleanup_proof": self.cleanup_proof,
                    "zero_entity_proof": self.zero_entity_proof,
                    "all_disabled_proof": self.all_disabled_proof,
                    "entities": self.original_ids,
                    "registry_preferences": self.original_preferences,
                    "request_counts": {
                        "credential_grants": (await self.sim())["counts"]["password"],
                        "renewal_grants": (await self.sim())["counts"].get("refresh_token", 0),
                        "status_requests": (await self.sim())["counts"]["homestatus"],
                        "topology_requests": (await self.sim())["counts"]["homesdata"],
                        "authentication_requests": (await self.sim())["counts"]["token_requests"],
                    },
                    "budget_proof": self.budget_proof,
                    "setup_retry_proofs": self.retry_proofs,
                },
                indent=2,
            )
            + "\n"
        )


async def main():
    archive = Path("/opt/velux-active/velux_active.zip")
    digest = hashlib.sha256(await asyncio.to_thread(archive.read_bytes)).hexdigest()
    assert digest == os.environ["LAB_ARTIFACT_SHA256"]
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        await Lab(session).run()


if __name__ == "__main__":
    asyncio.run(main())
