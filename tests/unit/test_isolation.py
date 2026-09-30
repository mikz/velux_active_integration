"""Focused isolation regressions; runnable with stdlib unittest only."""

import copy
import unittest

from tests.lab.isolation import (
    IsolationError,
    validate_compose,
    validate_inspect,
    validate_routes,
)


def compose_fixture():
    return {
        "networks": {
            "lab": {
                "driver": "bridge",
                "internal": True,
                "enable_ipv6": False,
                "driver_opts": {"com.docker.network.bridge.gateway_mode_ipv4": "isolated"},
                "ipam": {"config": [{"subnet": "172.30.240.0/24"}]},
            }
        },
        "services": {
            "ha": {
                "image": "ha:pinned",
                "networks": {"lab": {}},
                "volumes": [
                    {"type": "bind", "source": "/tmp/ha-lab/artifacts", "target": "/artifacts"},
                    {"type": "volume", "source": "ha_config", "target": "/config"},
                ],
            }
        },
        "volumes": {"ha_config": {}},
    }


def inspect_fixture():
    network = {
        "Id": "network-id",
        "Name": "test-lab_lab",
        "Driver": "bridge",
        "Scope": "local",
        "Internal": True,
        "EnableIPv6": False,
        "Options": {"com.docker.network.bridge.gateway_mode_ipv4": "isolated"},
        "Labels": {"com.docker.compose.project": "test-lab", "com.docker.compose.network": "lab"},
        "Containers": {"ha-id": {}},
        "IPAM": {"Driver": "default", "Config": [{"Subnet": "172.30.240.0/24"}]},
    }
    container = {
        "Id": "ha-id",
        "HostConfig": {"NetworkMode": "test-lab_lab", "Runtime": "runc"},
        "Config": {"Labels": {"com.docker.compose.project": "test-lab"}},
        "NetworkSettings": {
            "Ports": {"8123/tcp": None},
            "Networks": {
                "test-lab_lab": {
                    "NetworkID": "network-id",
                    "IPAddress": "172.30.240.2",
                    "Gateway": "",
                }
            },
        },
        "Mounts": [{"Type": "volume", "Name": "test-lab_ha_config", "Driver": "local"}],
    }
    return network, [container]


def routes_fixture():
    rules = [
        {"priority": 0, "src": "all", "table": "local"},
        {"priority": 32766, "src": "all", "table": "main"},
    ]
    return {
        "addresses": [
            {
                "ifname": "lo",
                "addr_info": [
                    {"local": "127.0.0.1", "prefixlen": 8},
                    {"local": "::1", "prefixlen": 128},
                ],
            },
            {"ifname": "eth0", "addr_info": [{"local": "172.30.240.2", "prefixlen": 24}]},
        ],
        "ipv4_routes": [
            {"dst": "172.30.240.0/24", "dev": "eth0", "scope": "link"},
            {"type": "local", "dst": "127.0.0.0/8", "dev": "lo", "table": "local"},
            {"type": "local", "dst": "172.30.240.2", "dev": "eth0", "table": "local"},
        ],
        "ipv6_routes": [{"type": "local", "dst": "::1", "dev": "lo", "table": "local"}],
        "ipv4_rules": copy.deepcopy(rules),
        "ipv6_rules": copy.deepcopy(rules),
    }


class ComposeIsolationTests(unittest.TestCase):
    def validate(self, config):
        validate_compose(config, allowed_bind_mounts=["/tmp/ha-lab/artifacts"])

    def test_permits_isolated_project_with_explicit_mounts(self):
        self.validate(compose_fixture())

    def test_forbids_network_escapes(self):
        for key, value in [
            ("internal", False),
            ("enable_ipv6", True),
            ("external", True),
            ("driver", "host"),
        ]:
            with self.subTest(key=key):
                config = compose_fixture()
                config["networks"]["lab"][key] = value
                with self.assertRaises(IsolationError):
                    self.validate(config)
        config = compose_fixture()
        config["networks"]["lab"]["driver_opts"]["com.docker.network.bridge.name"] = "docker0"
        with self.assertRaises(IsolationError):
            self.validate(config)

    def test_forbids_service_escape_configuration(self):
        bad = {
            "networks": {"lab": {}, "default": {}},
            "network_mode": "host",
            "ports": [{"target": 8123, "published": "8123"}],
            "privileged": True,
            "cap_add": ["NET_ADMIN"],
            "devices": ["/dev/ttyUSB0"],
            "security_opt": ["seccomp:unconfined"],
            "pid": "host",
            "use_api_socket": True,
            "extra_hosts": ["host.docker.internal:host-gateway"],
            "dns": ["192.168.1.1"],
            "environment": {"HTTP_PROXY": "http://proxy:3128"},
            "sysctls": {"net.ipv4.ip_forward": "1"},
            "logging": {"driver": "syslog", "options": {"syslog-address": "tcp://host:514"}},
        }
        for key, value in bad.items():
            with self.subTest(key=key):
                config = compose_fixture()
                config["services"]["ha"][key] = value
                with self.assertRaises(IsolationError):
                    self.validate(config)

    def test_forbids_endpoint_driver_overrides(self):
        config = compose_fixture()
        config["services"]["ha"]["networks"]["lab"]["driver_opts"] = {
            "com.docker.network.endpoint.sysctls": "net.ipv4.conf.IFNAME.forwarding=1"
        }
        with self.assertRaises(IsolationError):
            self.validate(config)

    def test_bind_allowlist_is_exact(self):
        config = compose_fixture()
        config["services"]["ha"]["volumes"][0]["source"] += "/other"
        with self.assertRaisesRegex(IsolationError, "unapproved bind"):
            self.validate(config)

    def test_forbids_volume_driver_escape(self):
        for volume in (
            {"external": True},
            {"driver": "nfs"},
            {"driver_opts": {"device": "/", "o": "bind", "type": "none"}},
        ):
            with self.subTest(volume=volume):
                config = compose_fixture()
                config["volumes"]["ha_config"] = volume
                with self.assertRaises(IsolationError):
                    self.validate(config)


class InspectIsolationTests(unittest.TestCase):
    def validate(self, network, containers):
        validate_inspect(
            network,
            containers,
            expected_project="test-lab",
            expected_container_ids=["ha-id"],
            allowed_volume_names=["test-lab_ha_config"],
        )

    def test_permits_unpublished_image_expose(self):
        self.validate(*inspect_fixture())

    def test_detects_added_foreign_member(self):
        network, containers = inspect_fixture()
        network["Containers"]["foreign"] = {}
        with self.assertRaisesRegex(IsolationError, "unexpected network members"):
            self.validate(network, containers)

    def test_detects_runtime_mutations(self):
        for key, value in {
            "Privileged": True,
            "CapAdd": ["SYS_ADMIN"],
            "PortBindings": {"8123/tcp": [{"HostPort": "8123"}]},
            "NetworkMode": "host",
            "DeviceRequests": [{"Driver": "nvidia"}],
        }.items():
            with self.subTest(key=key):
                network, containers = inspect_fixture()
                containers[0]["HostConfig"][key] = value
                with self.assertRaises(IsolationError):
                    self.validate(network, containers)

    def test_detects_extra_network_and_gateway(self):
        for change in ("extra", "gateway"):
            with self.subTest(change=change):
                network, containers = inspect_fixture()
                attached = containers[0]["NetworkSettings"]["Networks"]
                if change == "extra":
                    attached["bridge"] = {}
                else:
                    attached["test-lab_lab"]["Gateway"] = "172.30.240.1"
                with self.assertRaises(IsolationError):
                    self.validate(network, containers)

    def test_detects_unapproved_runtime_volume(self):
        network, containers = inspect_fixture()
        containers[0]["Mounts"][0]["Name"] = "production_config"
        with self.assertRaisesRegex(IsolationError, "unapproved runtime volume"):
            self.validate(network, containers)


class RouteIsolationTests(unittest.TestCase):
    def validate(self, snapshot):
        validate_routes(snapshot, subnet="172.30.240.0/24", ipv4_address="172.30.240.2")

    def test_permits_only_connected_and_loopback_routes(self):
        self.validate(routes_fixture())

    def test_forbids_gateway_external_route_and_policy(self):
        bad_routes = [
            {"dst": "default", "gateway": "172.30.240.1", "dev": "eth0"},
            {"dst": "192.168.65.254/32", "dev": "eth0"},
            {"dst": "172.30.240.0/24", "dev": "eth0", "scope": "link", "table": 123},
            {"dst": "172.30.240.0/24", "dev": "eth0", "nexthops": [{"dev": "eth0"}]},
        ]
        for route in bad_routes:
            with self.subTest(route=route):
                snapshot = routes_fixture()
                snapshot["ipv4_routes"].append(route)
                with self.assertRaises(IsolationError):
                    self.validate(snapshot)
        snapshot = routes_fixture()
        snapshot["ipv4_rules"].append({"priority": 100, "src": "all", "table": 123})
        with self.assertRaises(IsolationError):
            self.validate(snapshot)

    def test_forbids_ipv6_even_link_local(self):
        snapshot = routes_fixture()
        snapshot["addresses"][1]["addr_info"].append({"local": "fe80::1", "prefixlen": 64})
        with self.assertRaises(IsolationError):
            self.validate(snapshot)

    def test_forbids_extra_interface(self):
        snapshot = routes_fixture()
        snapshot["addresses"].append({"ifname": "eth1", "addr_info": []})
        with self.assertRaises(IsolationError):
            self.validate(snapshot)

    def test_incomplete_evidence_fails(self):
        for key in routes_fixture():
            with self.subTest(key=key):
                snapshot = routes_fixture()
                del snapshot[key]
                with self.assertRaises(IsolationError):
                    self.validate(snapshot)


if __name__ == "__main__":
    unittest.main()
