"""Tool call interceptor and chaos harness for wrapping agent tools."""

from __future__ import annotations

import asyncio
import functools
import inspect
import time
from contextvars import ContextVar
from typing import Any, Callable, Dict, Optional, Union

from agent_chaos.core.faults import Fault, FaultType
from agent_chaos.core.trajectory import TrajectoryRecorder

# ContextVar for keeping track of the currently active harness in the async/thread context
_active_harness: ContextVar[Optional["ChaosHarness"]] = ContextVar("_active_harness", default=None)


def get_current_harness() -> Optional["ChaosHarness"]:
    """Retrieve the currently active ChaosHarness in context."""
    return _active_harness.get()


class ChaosHarness:
    """Manages tool interception, fault assignment, and trajectory recording."""

    def __init__(self, recorder: Optional[TrajectoryRecorder] = None) -> None:
        self.recorder = recorder or TrajectoryRecorder()
        self._fault_map: Dict[str, Fault] = {}
        self._fault_invocations: Dict[str, int] = {}
        self._token = None

    def set_fault(self, tool_name: str, fault: Fault) -> None:
        """Assign a fault rule to a tool name."""
        self._fault_map[tool_name] = fault
        self._fault_invocations[tool_name] = 0

    def remove_fault(self, tool_name: str) -> None:
        """Remove a fault rule for a tool."""
        self._fault_map.pop(tool_name, None)
        self._fault_invocations.pop(tool_name, None)

    def get_fault(self, tool_name: str) -> Optional[Fault]:
        """Get the configured fault for a tool, if any."""
        return self._fault_map.get(tool_name)

    def intercept(
        self,
        tool_name: Optional[str] = None,
        fault: Optional[Fault] = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator to intercept a tool callable (sync or async)."""
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            name = tool_name or func.__name__
            if fault:
                self.set_fault(name, fault)
            return self.wrap_tool(name, func)

        return decorator

    def wrap_tool(self, name: str, func: Callable[..., Any]) -> Callable[..., Any]:
        """Wrap an existing callable to record calls and inject configured faults."""
        is_async = asyncio.iscoroutinefunction(func)
        sig = inspect.signature(func)

        def _extract_args(args: tuple, kwargs: dict) -> Dict[str, Any]:
            bound = sig.bind_partial(*args, **kwargs)
            bound.apply_defaults()
            return dict(bound.arguments)

        if is_async:
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                args_dict = _extract_args(args, kwargs)
                fault = self.get_fault(name)

                start_time = time.perf_counter()
                injected_fault = None
                result = None
                error_msg = None

                try:
                    fault_count = self._fault_invocations.get(name, 0) + 1
                    if fault and fault.should_trigger(fault_count, args_dict):
                        self._fault_invocations[name] = fault_count
                        injected_fault = fault.fault_type
                        fault_res = await fault.apply_async()
                        if fault.fault_type == FaultType.LATENCY:
                            # Latency fault: sleep already happened, now execute real func
                            result = await func(*args, **kwargs)
                            return result
                        # For malformed or poisoned data, return the injected payload directly
                        result = fault_res
                        return result

                    # No fault or condition not met -> execute original tool
                    result = await func(*args, **kwargs)
                    return result
                except Exception as exc:
                    error_msg = str(exc)
                    raise
                finally:
                    duration_ms = (time.perf_counter() - start_time) * 1000
                    self.recorder.record_call(
                        tool_name=name,
                        arguments=args_dict,
                        duration_ms=duration_ms,
                        fault_injected=injected_fault,
                        result=result,
                        error=error_msg,
                    )

            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                args_dict = _extract_args(args, kwargs)
                fault = self.get_fault(name)

                start_time = time.perf_counter()
                injected_fault = None
                result = None
                error_msg = None

                try:
                    fault_count = self._fault_invocations.get(name, 0) + 1
                    if fault and fault.should_trigger(fault_count, args_dict):
                        self._fault_invocations[name] = fault_count
                        injected_fault = fault.fault_type
                        fault_res = fault.apply_sync()
                        if fault.fault_type == FaultType.LATENCY:
                            result = func(*args, **kwargs)
                            return result
                        result = fault_res
                        return result

                    result = func(*args, **kwargs)
                    return result
                except Exception as exc:
                    error_msg = str(exc)
                    raise
                finally:
                    duration_ms = (time.perf_counter() - start_time) * 1000
                    self.recorder.record_call(
                        tool_name=name,
                        arguments=args_dict,
                        duration_ms=duration_ms,
                        fault_injected=injected_fault,
                        result=result,
                        error=error_msg,
                    )

            return sync_wrapper

    def __enter__(self) -> "ChaosHarness":
        self._token = _active_harness.set(self)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._token:
            _active_harness.reset(self._token)
            self._token = None


def chaos_harness(
    tool: Optional[str] = None,
    fault: Optional[Fault] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Convenience decorator to run a function/test inside a ChaosHarness."""
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            harness = ChaosHarness()
            if tool and fault:
                harness.set_fault(tool, fault)
            with harness:
                return func(*args, harness=harness, **kwargs)

        return wrapper

    return decorator
