"""Salesforce Einstein Agent API client & session runner."""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional
import httpx
from pydantic import BaseModel, Field


class AgentforceConfig(BaseModel):
    """Configuration for connecting to Salesforce Agentforce Einstein Agent Runtime API."""
    instance_url: str  # e.g., "https://yourcompany.my.salesforce.com"
    access_token: str
    agent_id: str
    api_version: str = "v61.0"
    timeout_seconds: float = 30.0


class AgentTurnResult(BaseModel):
    """Result of a single conversational turn with an Agentforce agent."""
    turn_index: int
    user_query: str
    agent_response: str
    duration_seconds: float
    raw_payload: Dict[str, Any] = Field(default_factory=dict)
    timed_out: bool = False
    error: Optional[str] = None


class AgentforceClient:
    """HTTP client communicating with Salesforce's Einstein Agent API."""

    def __init__(self, config: AgentforceConfig) -> None:
        self.config = config
        self._session_id: Optional[str] = None

    @property
    def base_url(self) -> str:
        return self.config.instance_url.rstrip("/")

    def create_session(self) -> str:
        """Create a new conversational session with the specified Agentforce agent."""
        url = f"{self.base_url}/services/data/{self.config.api_version}/einstein/ai-agent/sessions"
        headers = {
            "Authorization": f"Bearer {self.config.access_token}",
            "Content-Type": "application/json",
        }
        payload = {"agentId": self.config.agent_id}

        with httpx.Client(timeout=self.config.timeout_seconds) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            self._session_id = data.get("sessionId") or data.get("id")
            return self._session_id or ""

    def send_message(self, user_text: str, turn_index: int = 1) -> AgentTurnResult:
        """Send a message turn to the Agentforce agent and await the response."""
        if not self._session_id:
            self.create_session()

        url = f"{self.base_url}/services/data/{self.config.api_version}/einstein/ai-agent/sessions/{self._session_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.config.access_token}",
            "Content-Type": "application/json",
        }
        payload = {"message": user_text}

        start_t = time.perf_counter()
        try:
            with httpx.Client(timeout=self.config.timeout_seconds) as client:
                resp = client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                duration = time.perf_counter() - start_t

                # Extract response text from Agent API payload structure
                agent_text = (
                    data.get("message", {}).get("content")
                    or data.get("response")
                    or json.dumps(data)
                )

                return AgentTurnResult(
                    turn_index=turn_index,
                    user_query=user_text,
                    agent_response=agent_text,
                    duration_seconds=duration,
                    raw_payload=data,
                    timed_out=False,
                )
        except httpx.TimeoutException as exc:
            duration = time.perf_counter() - start_t
            return AgentTurnResult(
                turn_index=turn_index,
                user_query=user_text,
                agent_response="",
                duration_seconds=duration,
                timed_out=True,
                error=f"Timeout after {duration:.1f}s: {exc}",
            )
        except Exception as exc:
            duration = time.perf_counter() - start_t
            return AgentTurnResult(
                turn_index=turn_index,
                user_query=user_text,
                agent_response="",
                duration_seconds=duration,
                timed_out=False,
                error=str(exc),
            )
