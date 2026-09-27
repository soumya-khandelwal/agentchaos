"""Unified Runtime Guard protecting tools with Circuit Breakers, Rate Limiters, and HITL."""

from __future__ import annotations

import asyncio
import functools
import inspect
import time
from typing import Any, Callable, Dict, Optional, Union

from agent_chaos.guard.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError, CircuitState
from agent_chaos.guard.hitl import HITLApprovalError, HITLDecision, HITLGate
from agent_chaos.guard.rate_limiter import RateLimitExceededError, SlidingWindowRateLimiter


class GuardDecision:
    """Outcome of evaluating a tool invocation against active runtime guardrails."""
    def __init__(
        self,
        allowed: bool,
        reason: Optional[str] = None,
        circuit_state: Optional[CircuitState] = None,
        rate_usage: Optional[int] = None,
    ):
        self.allowed = allowed
        self.reason = reason
        self.circuit_state = circuit_state
        self.rate_usage = rate_usage


class RuntimeGuard:
    """In-line runtime guard protecting agent tools from runaway loops, cascades, and unauthorized mutations."""

    def __init__(self) -> None:
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.rate_limiters: Dict[str, SlidingWindowRateLimiter] = {}
        self.hitl_gate = HITLGate()

    def configure_circuit_breaker(
        self,
        tool_name: str,
        failure_threshold: int = 3,
        recovery_timeout: float = 10.0,
    ) -> CircuitBreaker:
        """Set up a circuit breaker for a tool."""
        cb = CircuitBreaker(
            tool_name=tool_name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
        )
        self.circuit_breakers[tool_name] = cb
        return cb

    def configure_rate_limit(
        self,
        tool_name: str,
        max_calls: int = 10,
        window_seconds: float = 60.0,
    ) -> SlidingWindowRateLimiter:
        """Set up a sliding-window rate limit for a tool."""
        limiter = SlidingWindowRateLimiter(max_calls=max_calls, window_seconds=window_seconds)
        self.rate_limiters[tool_name] = limiter
        return limiter

    def configure_hitl(
        self,
        tool_name: str,
        condition: Optional[Callable[[Dict[str, Any]], bool]] = None,
        prompt_message: str = "Sensitive operation requires authorization",
    ) -> None:
        """Require human approval for sensitive invocations of a tool."""
        self.hitl_gate.add_policy(tool_name, condition=condition, prompt_message=prompt_message)

    def check_call(self, tool_name: str, arguments: Dict[str, Any]) -> GuardDecision:
        """Evaluate all guardrails before an execution begins."""
        # 1. Check Circuit Breaker
        cb = self.circuit_breakers.get(tool_name)
        if cb and not cb.can_execute():
            retry_in = cb.time_until_retry()
            return GuardDecision(
                allowed=False,
                reason=f"Circuit breaker for tool '{tool_name}' is OPEN. Retry in {retry_in:.1f}s.",
                circuit_state=cb.state,
            )

        # 2. Check Rate Limiter
        limiter = self.rate_limiters.get(tool_name)
        if limiter and not limiter.check_and_record():
            return GuardDecision(
                allowed=False,
                reason=f"Rate limit exceeded for tool '{tool_name}' ({limiter.max_calls} calls/{limiter.window_seconds}s).",
                rate_usage=limiter.current_usage(),
            )

        # 3. Check Human-in-the-Loop Gate
        hitl_res = self.hitl_gate.evaluate(tool_name, arguments)
        if hitl_res == HITLDecision.REJECTED:
            return GuardDecision(
                allowed=False,
                reason=f"Action blocked: Human approval rejected for tool '{tool_name}'.",
            )

        return GuardDecision(
            allowed=True,
            circuit_state=cb.state if cb else None,
            rate_usage=limiter.current_usage() if limiter else None,
        )

    def record_result(self, tool_name: str, is_success: bool, error: Optional[Any] = None) -> None:
        """Update circuit breaker state based on tool outcome."""
        cb = self.circuit_breakers.get(tool_name)
        if cb:
            if is_success:
                cb.record_success()
            else:
                cb.record_failure(error)

    def wrap_tool(
        self,
        name: str,
        func: Optional[Callable[..., Any]] = None,
    ) -> Any:
        """Wrap a Python callable with RuntimeGuard protection.

        Can be used directly as wrap_tool(name, func) or as a decorator @wrap_tool(name).
        """
        def decorator(target_func: Callable[..., Any]) -> Callable[..., Any]:
            is_async = asyncio.iscoroutinefunction(target_func)
            sig = inspect.signature(target_func)

            def _extract_args(args: tuple, kwargs: dict) -> Dict[str, Any]:
                bound = sig.bind_partial(*args, **kwargs)
                bound.apply_defaults()
                return dict(bound.arguments)

            if is_async:
                @functools.wraps(target_func)
                async def async_guarded(*args: Any, **kwargs: Any) -> Any:
                    args_dict = _extract_args(args, kwargs)
                    decision = self.check_call(name, args_dict)
                    if not decision.allowed:
                        if decision.circuit_state == CircuitState.OPEN:
                            cb = self.circuit_breakers[name]
                            raise CircuitBreakerOpenError(name, cb.time_until_retry())
                        elif "Rate limit" in (decision.reason or ""):
                            limiter = self.rate_limiters[name]
                            raise RateLimitExceededError(name, limiter.max_calls, limiter.window_seconds)
                        else:
                            raise HITLApprovalError(name, decision.reason or "Rejected by guardrail")

                    try:
                        res = await target_func(*args, **kwargs)
                        self.record_result(name, is_success=True)
                        return res
                    except Exception as exc:
                        self.record_result(name, is_success=False, error=exc)
                        raise

                return async_guarded
            else:
                @functools.wraps(target_func)
                def sync_guarded(*args: Any, **kwargs: Any) -> Any:
                    args_dict = _extract_args(args, kwargs)
                    decision = self.check_call(name, args_dict)
                    if not decision.allowed:
                        if decision.circuit_state == CircuitState.OPEN:
                            cb = self.circuit_breakers[name]
                            raise CircuitBreakerOpenError(name, cb.time_until_retry())
                        elif "Rate limit" in (decision.reason or ""):
                            limiter = self.rate_limiters[name]
                            raise RateLimitExceededError(name, limiter.max_calls, limiter.window_seconds)
                        else:
                            raise HITLApprovalError(name, decision.reason or "Rejected by guardrail")

                    try:
                        res = target_func(*args, **kwargs)
                        self.record_result(name, is_success=True)
                        return res
                    except Exception as exc:
                        self.record_result(name, is_success=False, error=exc)
                        raise

                return sync_guarded

        if func is not None:
            return decorator(func)
        return decorator
