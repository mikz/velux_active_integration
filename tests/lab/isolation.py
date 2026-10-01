"""Fail-closed, read-only validation of the isolated Docker test lab.

The caller creates a fresh project, holds every application behind its startup
gate, and supplies effective Compose, Docker inspect, and iproute2 JSON output.
These helpers never contact Docker or change a namespace. An explicit mount
allowlist authorizes exact source paths, not their parents or descendants.
"""

from __future__ import annotations

import ipaddress
import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any


class IsolationError(ValueError):
    """A required isolation invariant is absent or unsafe."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise IsolationError(message)


def _map(value: Any, context: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), f"{context} must be an object")
    return value


def _empty(value: Any) -> bool:
    return value is None or value is False or value == [] or value == {} or value == ""


def _path(value: Any) -> str:
    _require(isinstance(value, (str, os.PathLike)), "bind source must be a path")
    path = Path(value)
    _require(path.is_absolute(), f"bind source must be absolute: {path}")
    return str(path.resolve())


def _bind_source(source: Any, allowed: set[str]) -> None:
    path = _path(source)
    _require(path in allowed, f"unapproved bind source: {path}")
    forbidden = tuple(
        str(Path(prefix).resolve()) for prefix in ("/proc", "/sys", "/dev", "/run", "/var/run")
    )
    _require(path != "/", "cannot bind the host filesystem root")
    _require(
        not any(path == prefix or path.startswith(prefix + "/") for prefix in forbidden),
        f"host system/socket mount is forbidden: {path}",
    )
    _require(not Path(path).is_socket(), f"host socket mount is forbidden: {path}")


def _settings(settings: Mapping[str, Any], *, inspect: bool) -> None:
    names = {
        "privileged": "Privileged",
        "cap_add": "CapAdd",
        "devices": "Devices",
        "device_cgroup_rules": "DeviceCgroupRules",
        "device_requests": "DeviceRequests",
        "ports": "PortBindings",
        "publish_all_ports": "PublishAllPorts",
        "extra_hosts": "ExtraHosts",
        "volumes_from": "VolumesFrom",
        "links": "Links",
        "external_links": "ExternalLinks",
        "use_api_socket": "UseApiSocket",
    }
    for compose_key, inspect_key in names.items():
        key = inspect_key if inspect else compose_key
        _require(_empty(settings.get(key)), f"{key} is forbidden")
    for compose_key, inspect_key, permitted in (
        ("pid", "PidMode", {None, "", "private"}),
        ("ipc", "IpcMode", {None, "", "private", "shareable"}),
        ("uts", "UTSMode", {None, "", "private"}),
        ("userns_mode", "UsernsMode", {None, "", "private"}),
        ("cgroup", "CgroupnsMode", {None, "", "private"}),
        ("runtime", "Runtime", {None, "", "runc"}),
    ):
        key = inspect_key if inspect else compose_key
        _require(settings.get(key) in permitted, f"unsafe {key}")
    security_key = "SecurityOpt" if inspect else "security_opt"
    permitted_security = {"no-new-privileges", "no-new-privileges:true"}
    _require(
        all(item in permitted_security for item in settings.get(security_key) or []),
        f"unsafe {security_key}",
    )
    sysctls = _map(settings.get("Sysctls" if inspect else "sysctls") or {}, "sysctls")
    allowed_sysctls = {
        "net.ipv6.conf.all.disable_ipv6",
        "net.ipv6.conf.default.disable_ipv6",
        "net.ipv6.conf.eth0.disable_ipv6",
    }
    _require(
        all(key in allowed_sysctls and str(value) == "1" for key, value in sysctls.items()),
        "only IPv6-disabling sysctls are permitted",
    )
    dns = settings.get("Dns" if inspect else "dns") or []
    if isinstance(dns, str):
        dns = [dns]
    _require(all(server == "127.0.0.1" for server in dns), "external custom DNS is forbidden")
    searches = settings.get("DnsSearch" if inspect else "dns_search") or []
    if isinstance(searches, str):
        searches = [searches]
    _require(all(search == "." for search in searches), "DNS search domains are forbidden")
    logging = _map(settings.get("LogConfig" if inspect else "logging") or {}, "logging")
    driver = logging.get("Type" if inspect else "driver")
    _require(driver in {None, "", "json-file", "local", "none"}, "external log driver forbidden")


def _environment(environment: Any) -> None:
    if isinstance(environment, Mapping):
        entries = environment.items()
    else:
        entries = (item.partition("=")[::2] for item in environment or [])
    forbidden = {"http_proxy", "https_proxy", "all_proxy", "ftp_proxy", "docker_host"}
    for key, value in entries:
        _require(key.lower() not in forbidden or not value, f"external transport env: {key}")


def _network_options(options: Mapping[str, Any]) -> None:
    expected = {
        "com.docker.network.bridge.gateway_mode_ipv4": {"isolated"},
        "com.docker.network.bridge.gateway_mode_ipv6": {"isolated"},
        "com.docker.network.bridge.enable_icc": {"true"},
        "com.docker.network.bridge.enable_ip_masquerade": {"false"},
    }
    _require(
        options.get("com.docker.network.bridge.gateway_mode_ipv4") == "isolated",
        "IPv4 gateway mode must be isolated",
    )
    for key, value in options.items():
        _require(key in expected and value in expected[key], f"unsafe network option: {key}")


def _subnet(value: Any) -> ipaddress.IPv4Network:
    try:
        subnet = ipaddress.ip_network(value)
    except (ValueError, TypeError) as exc:
        raise IsolationError("invalid lab subnet") from exc
    private_ranges = [
        ipaddress.ip_network(cidr) for cidr in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
    ]
    _require(
        isinstance(subnet, ipaddress.IPv4Network)
        and any(subnet.subnet_of(parent) for parent in private_ranges),
        "lab subnet must be an RFC 1918 IPv4 subnet",
    )
    return subnet


def validate_compose(
    config: Mapping[str, Any],
    *,
    network_key: str = "lab",
    allowed_bind_mounts: Iterable[str | os.PathLike[str]] = (),
) -> None:
    """Validate ``docker compose config --format json`` before creation.

    Build sections are allowed: the caller must use ``--no-build --pull never``
    for the isolated run. Only explicit local named volumes and exact approved
    bind sources can be mounted. All service profiles are checked.
    """
    allowed = {_path(path) for path in allowed_bind_mounts}
    networks = _map(config.get("networks"), "networks")
    _require(set(networks) == {network_key}, "exactly one lab network is required")
    network = _map(networks[network_key], "lab network")
    _require(network.get("driver") == "bridge", "lab driver must be bridge")
    _require(network.get("internal") is True, "lab network must be internal")
    _require(network.get("enable_ipv6") is False, "IPv6 must be explicitly disabled")
    _require(network.get("enable_ipv4", True) is True, "IPv4 must be enabled")
    for key in ("external", "attachable"):
        _require(not network.get(key), f"network {key} is forbidden")
    _network_options(_map(network.get("driver_opts"), "network options"))
    ipam = _map(network.get("ipam") or {}, "IPAM")
    _require(ipam.get("driver", "default") == "default", "custom IPAM is forbidden")
    _require(not ipam.get("options"), "custom IPAM options are forbidden")
    for pool in ipam.get("config") or []:
        _require(set(pool) <= {"subnet", "ip_range"}, "IPAM gateways/aux addresses forbidden")
        subnet = _subnet(pool.get("subnet"))
        if pool.get("ip_range"):
            _require(_subnet(pool["ip_range"]).subnet_of(subnet), "IP range outside lab subnet")
    _require(len(ipam.get("config") or []) <= 1, "only one IPv4 subnet is permitted")
    volumes = _map(config.get("volumes") or {}, "volumes")
    for name, value in volumes.items():
        volume = _map(value or {}, f"volume {name}")
        _require(not volume.get("external"), f"external volume forbidden: {name}")
        _require(volume.get("driver", "local") == "local", f"remote volume driver: {name}")
        _require(not volume.get("driver_opts"), f"volume driver options forbidden: {name}")
    _require(not config.get("secrets"), "host secrets are forbidden")
    _require(not config.get("configs"), "implicit config mounts are forbidden")
    services = _map(config.get("services"), "services")
    _require(bool(services), "at least one service is required")
    for name, service in services.items():
        service = _map(service, f"service {name}")
        _settings(service, inspect=False)
        _environment(service.get("environment"))
        _require(not service.get("network_mode"), f"network_mode forbidden: {name}")
        attached = service.get("networks")
        _require(isinstance(attached, (Mapping, list)), f"explicit lab network needed: {name}")
        _require(set(attached) == {network_key}, f"service {name} has extra/missing networks")
        if isinstance(attached, Mapping):
            endpoint = _map(attached[network_key] or {}, "Compose endpoint")
            for key in ("driver_opts", "link_local_ips", "ipv6_address"):
                _require(not endpoint.get(key), f"unsafe endpoint {key}")
        _require(not service.get("gpus"), f"GPU device access forbidden: {name}")
        _require(not service.get("secrets") and not service.get("configs"), "implicit mounts")
        reservations = (service.get("deploy") or {}).get("resources", {}).get("reservations", {})
        _require(not reservations.get("devices"), f"device reservations forbidden: {name}")
        for mount in service.get("volumes") or []:
            mount = _map(mount, "effective Compose mount")
            kind = mount.get("type")
            if kind == "bind":
                _bind_source(mount.get("source"), allowed)
            elif kind == "volume":
                _require(mount.get("source") in volumes, "undeclared/anonymous volume")
            else:
                _require(kind == "tmpfs", f"unsupported mount type: {kind}")


def validate_inspect(
    network: Mapping[str, Any],
    containers: list[Mapping[str, Any]],
    *,
    expected_project: str,
    expected_container_ids: Iterable[str],
    network_key: str = "lab",
    allowed_bind_mounts: Iterable[str | os.PathLike[str]] = (),
    allowed_volume_names: Iterable[str] = (),
) -> None:
    """Validate network/container inspect output while startup gates are held.

    Expected IDs and volume names must come from this fresh project's creation,
    never from the network's membership list being validated.
    """
    allowed = {_path(path) for path in allowed_bind_mounts}
    allowed_volumes = set(allowed_volume_names)
    expected_ids = set(expected_container_ids)
    _require(bool(expected_project) and bool(expected_ids), "explicit project and IDs required")
    _require(network.get("Driver") == "bridge", "runtime driver must be bridge")
    _require(network.get("Scope") == "local", "runtime network must be local")
    _require(network.get("Internal") is True, "runtime network is not internal")
    _require(network.get("EnableIPv6") is False, "runtime IPv6 enabled or unknown")
    _require(network.get("EnableIPv4", True) is True, "runtime IPv4 disabled")
    _require(not network.get("Ingress"), "ingress network forbidden")
    _require(not network.get("Attachable"), "attachable runtime network forbidden")
    _network_options(_map(network.get("Options"), "runtime network options"))
    labels = _map(network.get("Labels"), "network labels")
    _require(labels.get("com.docker.compose.project") == expected_project, "wrong project")
    _require(labels.get("com.docker.compose.network") == network_key, "wrong network label")
    network_id, network_name = network.get("Id"), network.get("Name")
    _require(bool(network_id) and bool(network_name), "network identity missing")
    _require(set(network.get("Containers") or {}) == expected_ids, "unexpected network members")
    actual_ids = [container.get("Id") for container in containers]
    _require(
        len(actual_ids) == len(expected_ids) and set(actual_ids) == expected_ids,
        "inspect container IDs differ from expected members",
    )
    ipam = _map(network.get("IPAM"), "runtime IPAM")
    _require(ipam.get("Driver") == "default" and not ipam.get("Options"), "unsafe runtime IPAM")
    pools = ipam.get("Config") or []
    _require(len(pools) == 1, "exactly one runtime IPv4 subnet required")
    subnet = _subnet(pools[0].get("Subnet"))
    _require(not pools[0].get("Gateway"), "isolated network has a gateway")
    _require(not pools[0].get("AuxiliaryAddresses"), "unexpected auxiliary addresses")
    for container in containers:
        host = _map(container.get("HostConfig"), "HostConfig")
        _settings(host, inspect=True)
        _require(host.get("NetworkMode") in {network_id, network_name}, "wrong network mode")
        config = _map(container.get("Config"), "container Config")
        _environment(config.get("Env"))
        labels = _map(config.get("Labels"), "container labels")
        _require(labels.get("com.docker.compose.project") == expected_project, "foreign container")
        settings = _map(container.get("NetworkSettings"), "NetworkSettings")
        _require(not any((settings.get("Ports") or {}).values()), "published runtime ports")
        attached = _map(settings.get("Networks"), "runtime attachments")
        _require(set(attached) == {network_name}, "extra/missing runtime networks")
        endpoint = _map(attached[network_name], "runtime endpoint")
        _require(endpoint.get("NetworkID") == network_id, "wrong endpoint network ID")
        for key in ("Gateway", "IPv6Gateway", "GlobalIPv6Address", "Links", "DriverOpts"):
            _require(not endpoint.get(key), f"unexpected endpoint {key}")
        try:
            address = ipaddress.IPv4Address(endpoint.get("IPAddress"))
        except (ValueError, TypeError) as exc:
            raise IsolationError("missing/invalid endpoint IPv4 address") from exc
        _require(address in subnet, "endpoint address outside lab")
        for mount in container.get("Mounts") or []:
            kind = mount.get("Type")
            if kind == "bind":
                _bind_source(mount.get("Source"), allowed)
            elif kind == "volume":
                _require(mount.get("Name") in allowed_volumes, "unapproved runtime volume")
                _require(mount.get("Driver") == "local", "nonlocal runtime volume")
            else:
                _require(kind == "tmpfs", f"unsupported runtime mount: {kind}")


def _table(value: Any) -> str:
    return {253: "default", 254: "main", 255: "local"}.get(value, str(value))


def validate_routes(snapshot: Mapping[str, Any], *, subnet: str, ipv4_address: str) -> None:
    """Validate complete iproute2 JSON from one actual runtime namespace.

    Required list fields: addresses (``ip -j address show``), ipv4_routes and
    ipv6_routes (``ip -j -4/-6 route show table all``), ipv4_rules and ipv6_rules
    (``ip -j -4/-6 rule show``). Validate every container before opening its gate.
    """
    lab = _subnet(subnet)
    try:
        address = ipaddress.IPv4Address(ipv4_address)
    except (ValueError, TypeError) as exc:
        raise IsolationError("invalid expected endpoint address") from exc
    _require(address in lab, "expected endpoint address outside lab")
    for key in ("addresses", "ipv4_routes", "ipv6_routes", "ipv4_rules", "ipv6_rules"):
        _require(isinstance(snapshot.get(key), list), f"missing complete route snapshot: {key}")
    interfaces = snapshot["addresses"]
    names = [item.get("ifname") for item in interfaces]
    _require(len(names) == 2 and len(set(names)) == 2 and "lo" in names, "unexpected interfaces")
    interface = next(name for name in names if name != "lo")
    found_address = False
    for item in interfaces:
        for info in item.get("addr_info") or []:
            try:
                ip = ipaddress.ip_address(info.get("local"))
            except (ValueError, TypeError) as exc:
                raise IsolationError("invalid interface address") from exc
            if item["ifname"] == "lo":
                _require(
                    ip in (ipaddress.ip_address("127.0.0.1"), ipaddress.ip_address("::1")),
                    "unexpected loopback address",
                )
            else:
                _require(
                    ip == address and info.get("prefixlen") == lab.prefixlen,
                    "unexpected address/IPv6 on lab interface",
                )
                found_address = True
    _require(found_address, "expected lab address absent")
    for family in ("ipv4", "ipv6"):
        seen_rules = set()
        for rule in snapshot[family + "_rules"]:
            _require(
                set(rule) <= {"priority", "src", "dst", "table", "protocol", "action"},
                "nonstandard routing policy fields",
            )
            table = _table(rule.get("table"))
            pair = (rule.get("priority"), table)
            _require(
                pair in {(0, "local"), (32766, "main"), (32767, "default")},
                "nonstandard routing policy",
            )
            _require(
                rule.get("src", "all") == "all" and rule.get("dst", "all") == "all",
                "selective routing policy",
            )
            _require(rule.get("action", "to_tbl") in {"to_tbl", "lookup"}, "routing action")
            _require(pair not in seen_rules, "duplicate routing policy")
            seen_rules.add(pair)
        _require({(0, "local"), (32766, "main")} <= seen_rules, "default routing policy absent")
    found_connected = False
    for family in ("ipv4", "ipv6"):
        for route in snapshot[family + "_routes"]:
            _require(
                _table(route.get("table", "main")) in {"local", "main", "default"},
                "unexpected routing table",
            )
            _require(
                not any(route.get(key) for key in ("gateway", "via", "nexthops", "nhid", "encap")),
                "gateway, multipath, or encapsulated route",
            )
            route_type = route.get("type", "unicast")
            if route_type in {"unreachable", "blackhole", "prohibit", "throw"}:
                continue
            _require(route_type in {"unicast", "local", "broadcast"}, "unexpected route type")
            _require(route.get("dst") not in {None, "default"}, "default route forbidden")
            try:
                destination = ipaddress.ip_network(route["dst"], strict=False)
            except (ValueError, TypeError) as exc:
                raise IsolationError("invalid route destination") from exc
            expected_version = 4 if family == "ipv4" else 6
            _require(destination.version == expected_version, "wrong route address family")
            loopback = ipaddress.ip_network("127.0.0.0/8" if expected_version == 4 else "::1/128")
            if destination.subnet_of(loopback):
                _require(route.get("dev") == "lo", "loopback route outside loopback")
            else:
                _require(expected_version == 4 and destination.subnet_of(lab), "external route")
                _require(route.get("dev") == interface, "lab route uses wrong interface")
                if destination == lab and route_type == "unicast":
                    _require(route.get("scope") == "link", "lab route is not link-scoped")
                    found_connected = True
    _require(found_connected, "connected lab route absent")
