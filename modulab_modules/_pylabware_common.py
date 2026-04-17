"""Shared helpers for Modulab wrappers around PyLabware drivers."""

from __future__ import annotations

import importlib
import inspect
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Any, Dict, List, Optional


class PylabwareModuleMixin:
    """Reusable runtime adapter for wrapping PyLabware device classes."""

    PYLABWARE_MODULE: str = ""
    PYLABWARE_CLASS: str = ""
    DEFAULT_CONNECTION_MODE: str = "serial"

    def _init_pylabware_runtime(self) -> None:
        self._driver = None
        self._driver_lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pylabware")
        self._last_error: Optional[str] = None

    def _coerce_bool(self, value: Any, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "on", "y"}:
            return True
        if text in {"0", "false", "no", "off", "n"}:
            return False
        return default

    def _get_conn(self, *keys: str, default: Any = None) -> Any:
        for key in keys:
            value = self.get_connection_parameter(key, None)
            if value not in (None, ""):
                return value
        return default

    def _get_param(self, *keys: str, default: Any = None) -> Any:
        for key in keys:
            value = self.get_driver_parameter(key, None)
            if value not in (None, ""):
                return value
        return default

    def _load_driver_class(self):
        if not self.PYLABWARE_MODULE or not self.PYLABWARE_CLASS:
            raise RuntimeError("PYLABWARE_MODULE and PYLABWARE_CLASS must be set")
        module = importlib.import_module(self.PYLABWARE_MODULE)
        return getattr(module, self.PYLABWARE_CLASS)

    def _build_driver_kwargs(self, driver_cls) -> Dict[str, Any]:
        signature = inspect.signature(driver_cls.__init__)
        params = set(signature.parameters.keys())

        kwargs: Dict[str, Any] = {}

        if "device_name" in params:
            kwargs["device_name"] = self._get_param("device_name", default=self.display_name or self.template_id)

        if "connection_mode" in params:
            kwargs["connection_mode"] = self._get_conn("connection_mode", default=self.DEFAULT_CONNECTION_MODE)

        if "address" in params:
            kwargs["address"] = self._get_conn("address", "host", default=None)

        if "port" in params:
            kwargs["port"] = self._get_conn("port", "serial_port", default=None)

        if "user" in params:
            kwargs["user"] = self._get_conn("username", "user", default=None)

        if "password" in params:
            kwargs["password"] = self._get_conn("password", default=None)

        if "schema" in params:
            kwargs["schema"] = self._get_conn("schema", default=None)

        if "verify_ssl" in params:
            kwargs["verify_ssl"] = self._coerce_bool(self._get_conn("verify_ssl", default=False), default=False)

        if "switch_address" in params:
            kwargs["switch_address"] = self._get_param("switch_address", default=None)

        if "valve_type" in params:
            kwargs["valve_type"] = self._get_param("valve_type", default="3PORT_DISTR_IOBE")

        return kwargs

    def _connection_info(self) -> Dict[str, Any]:
        return {
            "connection_mode": self._get_conn("connection_mode", default=self.DEFAULT_CONNECTION_MODE),
            "address": self._get_conn("address", "host", default=None),
            "port": self._get_conn("port", "serial_port", default=None),
        }

    def _call_driver(self, method_name: str, *args: Any, timeout_s: Optional[float] = None, **kwargs: Any) -> Any:
        if self._driver is None:
            raise RuntimeError("Driver is not connected")

        func = getattr(self._driver, method_name, None)
        if func is None:
            raise ValueError(f"Driver method '{method_name}' is not available")

        timeout = timeout_s
        if timeout is None:
            timeout = float(self._get_param("command_timeout_s", default=20.0) or 20.0)

        with self._driver_lock:
            future = self._executor.submit(func, *args, **kwargs)
            try:
                return future.result(timeout=timeout)
            except FutureTimeoutError as exc:
                raise TimeoutError(f"Driver method '{method_name}' timed out") from exc

    def _call_driver_optional(self, method_name: str, *args: Any, default: Any = None, **kwargs: Any) -> Any:
        if self._driver is None:
            return default
        if not hasattr(self._driver, method_name):
            return default
        try:
            return self._call_driver(method_name, *args, **kwargs)
        except Exception:
            return default

    def _connect_pylabware(self) -> None:
        driver_cls = self._load_driver_class()
        kwargs = self._build_driver_kwargs(driver_cls)

        with self._driver_lock:
            self._driver = driver_cls(**kwargs)

        try:
            self._call_driver_optional("initialize_device")
            self.mark_connected(info=self._connection_info(), extra={"driver_class": self.PYLABWARE_CLASS})
            self._last_error = None
        except Exception as exc:
            self._last_error = str(exc)
            self.mark_disconnected(info=self._connection_info(), health="red", extra={"error": self._last_error})
            raise

    def _disconnect_pylabware(self) -> None:
        try:
            if self._driver is not None:
                for method_name in (
                    "stop",
                    "stop_stirring",
                    "stop_temperature_regulation",
                    "stop_pressure_regulation",
                    "stop_rotation",
                    "stop_bath",
                    "disconnect",
                ):
                    self._call_driver_optional(method_name, timeout_s=5.0)
        finally:
            with self._driver_lock:
                self._driver = None
            self.mark_disconnected(info=self._connection_info(), extra={"last_error": self._last_error})

    def _status_snapshot(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "driver_class": self.PYLABWARE_CLASS,
            "connected": bool(self._call_driver_optional("is_connected", default=False)),
            "idle": self._call_driver_optional("is_idle", default=None),
            "status": self._call_driver_optional("get_status", default=None),
            "last_error": self._last_error,
        }

        probes = [
            "get_temperature",
            "get_temperature_setpoint",
            "get_speed",
            "get_speed_setpoint",
            "get_pressure",
            "get_pressure_setpoint",
            "get_valve_position",
            "get_torque",
            "get_pump_speed",
            "get_pump_speed_setpoint",
        ]

        measurements: Dict[str, Any] = {}
        for probe in probes:
            value = self._call_driver_optional(probe, default=None)
            if value is not None:
                measurements[probe] = value

        if measurements:
            payload["measurements"] = measurements

        return payload

    def _start_operation(self) -> str:
        for method_name in (
            "start",
            "start_stirring",
            "start_temperature_regulation",
            "start_pressure_regulation",
            "start_rotation",
            "start_bath",
        ):
            if self._driver is not None and hasattr(self._driver, method_name):
                self._call_driver(method_name)
                return method_name
        raise ValueError("No start operation method available for this driver")

    def _stop_operation(self) -> str:
        for method_name in (
            "stop",
            "stop_stirring",
            "stop_temperature_regulation",
            "stop_pressure_regulation",
            "stop_rotation",
            "stop_bath",
        ):
            if self._driver is not None and hasattr(self._driver, method_name):
                self._call_driver(method_name)
                return method_name
        raise ValueError("No stop operation method available for this driver")


__all__: List[str] = ["PylabwareModuleMixin"]
