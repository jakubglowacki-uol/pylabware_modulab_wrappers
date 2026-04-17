"""Modulab wrapper for Tricontinent C3000 (PyLabware)."""

from __future__ import annotations

from typing import Any, Dict, List

from modulab_coordinator.driver_templates.simple import (
    SimpleDriverTemplate,
    build_simple_template,
    capability,
)

from modulab_modules._pylabware_common import PylabwareModuleMixin


class TricontinentC3000Template(PylabwareModuleMixin, SimpleDriverTemplate):
    """Thread-executor Modulab wrapper around C3000SyringePump."""

    # 1) Module identity and metadata
    template_id = "pylabware.tricontinent_c3000"
    interface_id = "ILiquidDispenser"
    display_name = "Tricontinent C3000"
    version = "1.0.0"
    description = "PyLabware-backed Modulab wrapper for Tricontinent C3000."
    vendor = "PyLabware"
    model = "C3000SyringePump"
    default_name = "Tricontinent C3000"
    tags = ("pylabware", "wrapper", "lab-device")
    metadata = {
        "subtype": "pylabware_wrapper",
        "driver_type": "python_wrapper",
        "interface_version": "1.0",
        "wrapper_style": "thread_executor",
    }

    # 2) Connection and configuration schema
    connection_type = "serial"
    connection_param_schema = {
        "connection_mode": {
            "type": "string",
            "description": "PyLabware connection mode (typically serial or tcp).",
            "required": False,
            "default": "serial",
        },
        "address": {
            "type": "string",
            "description": "Device address or host, depending on connection mode.",
            "required": False,
            "default": "",
        },
        "port": {
            "type": "string",
            "description": "Device port (serial device path or TCP port).",
            "required": False,
            "default": "",
        },
    }

    driver_param_schema = {
        "command_timeout_s": {
            "type": "float",
            "description": "Timeout for individual blocking driver method calls.",
            "required": False,
            "default": 20.0,
        },
        "device_name": {
            "type": "string",
            "description": "Optional PyLabware device name override.",
            "required": False,
            "default": "Tricontinent C3000",
        },
        "switch_address": {
            "type": "string",
            "description": "Switch address used by daisy-chained Tricontinent pumps.",
            "required": False,
            "default": "",
        },
        "valve_type": {
            "type": "string",
            "description": "Configured valve type for the connected pump head.",
            "required": False,
            "default": "3PORT_DISTR_IOBE",
        },
    }

    # 3) Instance state initialization
    PYLABWARE_MODULE = "PyLabware.devices.tricontinent_c3000"
    PYLABWARE_CLASS = "C3000SyringePump"
    DEFAULT_CONNECTION_MODE = "serial"

    def __init__(self, **kwargs: Dict[str, Any]) -> None:
        super().__init__(**kwargs)
        self._init_pylabware_runtime()
        self.mark_disconnected(info=self._connection_info(), extra={"driver_class": self.PYLABWARE_CLASS})

    # 4) Lifecycle hooks
    def connect(self) -> None:
        self._connect_pylabware()

    def disconnect(self) -> None:
        self._disconnect_pylabware()

    # 5) Capabilities
    @capability("get_status", exclusive=False)
    def _handle_get_status(self, _params: Dict[str, Any]) -> Dict[str, Any]:
        status = self._status_snapshot()
        self.update_status_extra({"pylabware": status})
        return {"success": True, **status}

    @capability(
        "invoke_method",
        inputs={
            "method": {"type": "string", "description": "PyLabware method name", "required": True},
            "args": {"type": "array", "description": "Positional arguments", "required": False},
            "kwargs": {"type": "object", "description": "Keyword arguments", "required": False},
        },
    )
    def _handle_invoke_method(self, params: Dict[str, Any]) -> Dict[str, Any]:
        method = str(params.get("method") or "").strip()
        if not method:
            raise ValueError("method is required")
        args = params.get("args") or []
        kwargs = params.get("kwargs") or {}
        if not isinstance(args, list):
            raise ValueError("args must be a list")
        if not isinstance(kwargs, dict):
            raise ValueError("kwargs must be an object")
        result = self._call_driver(method, *args, **kwargs)
        return {"success": True, "method": method, "result": result}

    @capability("start_operation")
    def _handle_start_operation(self, _params: Dict[str, Any]) -> Dict[str, Any]:
        method = self._start_operation()
        return {"success": True, "method": method}

    @capability("stop_operation")
    def _handle_stop_operation(self, _params: Dict[str, Any]) -> Dict[str, Any]:
        method = self._stop_operation()
        return {"success": True, "method": method}

    # 6) Internal helpers and telemetry sync
    def _sync_status(self) -> None:
        snapshot = self._status_snapshot()
        self.update_status_extra({"pylabware": snapshot})


DRIVER_TEMPLATE = build_simple_template(TricontinentC3000Template)

__all__: List[str] = ["DRIVER_TEMPLATE"]
