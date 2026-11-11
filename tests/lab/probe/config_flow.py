"""Native metadata for the synthetic secondary registry owner; no user setup."""

from homeassistant.config_entries import ConfigFlow


class LabProbeFlow(ConfigFlow, domain="lab_probe"):
    """Allow native entry metadata inspection without creating another lifecycle."""

    VERSION = 1
