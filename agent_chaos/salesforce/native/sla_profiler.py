"""Extensible Multi-Channel SLA Profiler for Salesforce Agentforce."""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field


class ChannelBudget(BaseModel):
    """SLA timeout budget specification for a specific Agentforce delivery channel."""
    channel_id: str
    display_name: str
    sla_seconds: float
    description: str


DEFAULT_CHANNEL_BUDGETS: Dict[str, ChannelBudget] = {
    "experience_cloud": ChannelBudget(
        channel_id="experience_cloud",
        display_name="Experience Cloud (MIAW)",
        sla_seconds=15.0,
        description="Messaging for In-App and Web client heartbeat SLA before connection drops",
    ),
    "slack": ChannelBudget(
        channel_id="slack",
        display_name="Slack Bot Integration",
        sla_seconds=25.0,
        description="Slack event delivery and interaction response SLA budget",
    ),
    "whatsapp": ChannelBudget(
        channel_id="whatsapp",
        display_name="WhatsApp / SMS",
        sla_seconds=20.0,
        description="Digital Engagement messaging gateway turnaround SLA",
    ),
    "builder": ChannelBudget(
        channel_id="builder",
        display_name="Agentforce Builder Debugger",
        sla_seconds=45.0,
        description="Internal Setup test debugger generous timeout window",
    ),
}


class ChannelEvaluation(BaseModel):
    channel_id: str
    channel_name: str
    budget_seconds: float
    duration_seconds: float
    passed: bool
    risk_level: str  # SAFE, AT_RISK, BREACHED


class MultiChannelSLAReport(BaseModel):
    duration_seconds: float
    channel_evaluations: List[ChannelEvaluation] = Field(default_factory=list)
    has_discrepancy: bool = False
    diagnosis: str = ""


class NativeSLAProfiler:
    """Evaluates agent turn latency against extensible channel SLA budgets."""

    def __init__(self, custom_budgets: Optional[Dict[str, ChannelBudget]] = None) -> None:
        self.budgets: Dict[str, ChannelBudget] = dict(DEFAULT_CHANNEL_BUDGETS)
        if custom_budgets:
            self.budgets.update(custom_budgets)

    def register_channel(self, channel_id: str, display_name: str, sla_seconds: float, description: str = "") -> None:
        """Dynamically register or override a channel SLA budget."""
        self.budgets[channel_id] = ChannelBudget(
            channel_id=channel_id,
            display_name=display_name,
            sla_seconds=sla_seconds,
            description=description,
        )

    def evaluate_duration(self, duration_seconds: float) -> MultiChannelSLAReport:
        """Evaluate a turn duration against all registered channel SLA budgets."""
        evals: List[ChannelEvaluation] = []
        builder_passed = False
        exp_cloud_passed = True

        for cid, budget in self.budgets.items():
            passed = duration_seconds <= budget.sla_seconds
            if cid == "builder":
                builder_passed = passed
            elif cid == "experience_cloud":
                exp_cloud_passed = passed

            # Calculate risk: if within 80% of SLA, AT_RISK
            if not passed:
                risk = "BREACHED"
            elif duration_seconds >= budget.sla_seconds * 0.8:
                risk = "AT_RISK"
            else:
                risk = "SAFE"

            evals.append(
                ChannelEvaluation(
                    channel_id=cid,
                    channel_name=budget.display_name,
                    budget_seconds=budget.sla_seconds,
                    duration_seconds=duration_seconds,
                    passed=passed,
                    risk_level=risk,
                )
            )

        # Detect the classic Builder vs Experience Cloud discrepancy
        has_discrepancy = builder_passed and not exp_cloud_passed

        if has_discrepancy:
            diagnosis = (
                f"⚠️ Discrepancy Alert! Turn took {duration_seconds:.2f}s: "
                f"Succeeds in Agentforce Builder ({self.budgets['builder'].sla_seconds:.0f}s), "
                f"but DROPS on Experience Cloud ({self.budgets['experience_cloud'].sla_seconds:.0f}s)!"
            )
        elif not builder_passed:
            diagnosis = f"❌ Critical Timeout: Turn took {duration_seconds:.2f}s, exceeding all channel budgets."
        else:
            diagnosis = f"✅ All Channel SLAs Respected: Turn completed in {duration_seconds:.2f}s."

        return MultiChannelSLAReport(
            duration_seconds=duration_seconds,
            channel_evaluations=evals,
            has_discrepancy=has_discrepancy,
            diagnosis=diagnosis,
        )
