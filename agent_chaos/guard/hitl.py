"""Human-in-the-Loop (HITL) approval gate for sensitive agent actions."""

from __future__ import annotations

from enum import Enum
from typing import Any, Callable, Dict, Optional, Set
from pydantic import BaseModel


class HITLDecision(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    SKIPPED = "skipped"


class HITLApprovalError(RuntimeError):
    """Raised when an action requires human authorization and is rejected or withheld."""
    def __init__(self, tool_name: str, reason: str = "Action rejected by human supervisor"):
        super().__init__(f"Human approval required for tool '{tool_name}': {reason}")
        self.tool_name = tool_name


class HITLPolicy(BaseModel):
    """Defines conditions under which an agent tool call must pause for human approval."""
    tool_name: str
    condition: Optional[Callable[[Dict[str, Any]], bool]] = None
    prompt_message: str = "Sensitive operation requires authorization"

    class Config:
        arbitrary_types_allowed = True


class HITLGate:
    """Manages sensitive tool gates requiring explicit human approval."""

    def __init__(self) -> None:
        self._policies: Dict[str, HITLPolicy] = {}
        self._handler: Optional[Callable[[str, Dict[str, Any]], bool]] = None

    def add_policy(
        self,
        tool_name: str,
        condition: Optional[Callable[[Dict[str, Any]], bool]] = None,
        prompt_message: str = "Sensitive operation requires authorization",
    ) -> None:
        """Register a human approval gate for a tool."""
        self._policies[tool_name] = HITLPolicy(
            tool_name=tool_name,
            condition=condition,
            prompt_message=prompt_message,
        )

    def set_approval_handler(self, handler: Callable[[str, Dict[str, Any]], bool]) -> None:
        """Set a custom approval handler (e.g., terminal prompt, Slack webhook, or test mock)."""
        self._handler = handler

    def requires_approval(self, tool_name: str, arguments: Dict[str, Any]) -> bool:
        """Evaluate if the call matches any active human approval policy."""
        policy = self._policies.get(tool_name)
        if not policy:
            return False
        if policy.condition is not None:
            return policy.condition(arguments)
        return True

    def evaluate(self, tool_name: str, arguments: Dict[str, Any]) -> HITLDecision:
        """Evaluate approval. If required, invokes handler or returns REJECTED."""
        if not self.requires_approval(tool_name, arguments):
            return HITLDecision.SKIPPED

        if self._handler is not None:
            approved = self._handler(tool_name, arguments)
            return HITLDecision.APPROVED if approved else HITLDecision.REJECTED

        # Default without handler: reject for safety
        return HITLDecision.REJECTED
