"""GitHub Chaos Adapter for AI Coding & Triage Agents."""

from __future__ import annotations

import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Union
from agent_chaos.core import ChaosHarness, Fault, ToolHTTPError
from agent_chaos.core.audit import UniversalAuditEvent, ProtocolType
from agent_chaos.github.faults import GitHubFaults
from agent_chaos.github.models import (
    GitHubIssue,
    GitHubPullRequest,
    GitHubFileContent,
    GitHubMergeResult,
)


class GitHubChaosHarness(ChaosHarness):
    """Chaos testing harness tailored for AI agents interacting with GitHub.
    
    Provides ready-to-use GitHub tool mocks, fault injection presets, and
    automatic UniversalAuditEvent logging for deterministic resilience auditing.
    """

    def __init__(self, repo: str = "owner/my-repo") -> None:
        super().__init__()
        self.repo = repo
        self.audit_events: List[UniversalAuditEvent] = []
        self._in_memory_issues: Dict[int, Dict[str, Any]] = {}
        self._in_memory_prs: Dict[int, Dict[str, Any]] = {}
        self._in_memory_files: Dict[str, Dict[str, Any]] = {}
        self._seed_default_state()

    def _seed_default_state(self) -> None:
        """Seed realistic mock repository data."""
        self._in_memory_issues[1] = {
            "id": 1001,
            "number": 1,
            "title": "Fix login crash on empty username",
            "body": "When user submits empty username, auth service crashes with 500.",
            "state": "open",
            "author": "octocat",
            "labels": [{"name": "bug"}],
            "comments_count": 2,
        }
        self._in_memory_prs[42] = {
            "id": 2042,
            "number": 42,
            "title": "Fix null pointer in auth controller",
            "body": "Resolves issue #1 with input sanitization.",
            "state": "open",
            "base_branch": "main",
            "head_branch": "fix/auth-null-check",
            "mergeable": True,
            "merged": False,
            "additions": 15,
            "deletions": 3,
        }
        self._in_memory_files["README.md"] = {
            "name": "README.md",
            "path": "README.md",
            "sha": "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391",
            "size": 520,
            "content": "# Sample Project\n\nAutomated AI repo management.",
            "encoding": "utf-8",
        }

    # -------------------------------------------------------------------------
    # Convenience Fault Injection
    # -------------------------------------------------------------------------

    def inject_rate_limit(
        self,
        tool_name: str = "get_issue",
        limit: int = 5000,
        remaining: int = 0,
        reset_in_seconds: int = 60,
    ) -> None:
        """Inject GitHub Primary Rate Limit (HTTP 403) on target tool."""
        fault = GitHubFaults.rate_limit_exceeded(
            limit=limit,
            remaining=remaining,
            reset_in_seconds=reset_in_seconds,
        )
        self.set_fault(tool_name, fault)

    def inject_secondary_rate_limit(
        self,
        tool_name: str = "create_pull_request",
        retry_after: int = 120,
    ) -> None:
        """Inject GitHub Secondary Rate Limit / Abuse Detection (HTTP 403)."""
        fault = GitHubFaults.secondary_rate_limit(retry_after=retry_after)
        self.set_fault(tool_name, fault)

    def inject_merge_conflict(
        self,
        pr_number: int = 42,
        base: str = "main",
        head: str = "feature/patch",
    ) -> None:
        """Inject a 409 Conflict when merging a pull request."""
        fault = GitHubFaults.merge_conflict(pr_number=pr_number, base=base, head=head)
        self.set_fault("merge_pull_request", fault)

    def inject_branch_protection(
        self,
        pr_number: int = 42,
        required_checks: Optional[List[str]] = None,
        missing_reviews: int = 1,
    ) -> None:
        """Inject 422 Unprocessable Entity when branch protection rules block PR merge."""
        fault = GitHubFaults.branch_protection_failed(
            pr_number=pr_number,
            required_checks=required_checks,
            missing_reviews=missing_reviews,
        )
        self.set_fault("merge_pull_request", fault)

    def inject_not_found(
        self,
        tool_name: str = "get_issue",
        resource: str = "issue",
        identifier: Union[str, int] = 404,
    ) -> None:
        """Inject 404 Not Found error."""
        fault = GitHubFaults.not_found(resource=resource, identifier=identifier)
        self.set_fault(tool_name, fault)

    def inject_prompt_injection(
        self,
        issue_number: int = 1,
        injection_payload: Optional[str] = None,
    ) -> None:
        """Inject indirect prompt injection payload into issue body."""
        fault = GitHubFaults.prompt_injection_in_issue(
            issue_number=issue_number,
            injection_payload=injection_payload,
        )
        self.set_fault("get_issue", fault)

    # -------------------------------------------------------------------------
    # Pre-built Standard GitHub Tools
    # -------------------------------------------------------------------------

    def get_issue(self, repo: str, issue_number: int) -> Dict[str, Any]:
        """Fetch issue details."""
        if issue_number not in self._in_memory_issues:
            raise ToolHTTPError(
                status_code=404,
                message=f"Issue #{issue_number} not found in {repo}",
                payload={"status": 404, "message": "Not Found"},
            )
        return dict(self._in_memory_issues[issue_number])

    def create_issue(
        self,
        repo: str,
        title: str,
        body: str,
        labels: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create a new issue."""
        new_num = max(self._in_memory_issues.keys(), default=0) + 1
        record = {
            "id": 1000 + new_num,
            "number": new_num,
            "title": title,
            "body": body,
            "state": "open",
            "author": "agent-bot",
            "labels": [{"name": l} for l in (labels or [])],
            "comments_count": 0,
        }
        self._in_memory_issues[new_num] = record
        return dict(record)

    def create_pull_request(
        self,
        repo: str,
        title: str,
        head: str,
        base: str = "main",
        body: str = "",
    ) -> Dict[str, Any]:
        """Create a pull request."""
        new_pr_num = max(self._in_memory_prs.keys(), default=0) + 1
        record = {
            "id": 2000 + new_pr_num,
            "number": new_pr_num,
            "title": title,
            "body": body,
            "state": "open",
            "base_branch": base,
            "head_branch": head,
            "mergeable": True,
            "merged": False,
            "additions": 5,
            "deletions": 1,
        }
        self._in_memory_prs[new_pr_num] = record
        return dict(record)

    def merge_pull_request(
        self,
        repo: str,
        pr_number: int,
        commit_message: Optional[str] = None,
        merge_method: str = "merge",
    ) -> Dict[str, Any]:
        """Merge a pull request."""
        if pr_number not in self._in_memory_prs:
            raise ToolHTTPError(
                status_code=404,
                message=f"Pull request #{pr_number} not found",
                payload={"status": 404, "message": "Not Found"},
            )
        pr = self._in_memory_prs[pr_number]
        pr["merged"] = True
        pr["state"] = "closed"
        sha = "a1b2c3d4e5f678901234567890abcdef12345678"
        pr["merge_commit_sha"] = sha
        return {
            "sha": sha,
            "merged": True,
            "message": f"Pull Request successfully merged ({merge_method})",
        }

    def get_file_contents(
        self,
        repo: str,
        path: str,
        ref: str = "main",
    ) -> Dict[str, Any]:
        """Fetch raw contents of a file."""
        if path not in self._in_memory_files:
            raise ToolHTTPError(
                status_code=404,
                message=f"File '{path}' not found at ref '{ref}'",
                payload={"status": 404, "message": "Not Found"},
            )
        return dict(self._in_memory_files[path])

    def update_file(
        self,
        repo: str,
        path: str,
        content: str,
        message: str,
        branch: str = "main",
    ) -> Dict[str, Any]:
        """Create or update a repository file."""
        new_sha = uuid.uuid4().hex[:40]
        record = {
            "name": path.split("/")[-1],
            "path": path,
            "sha": new_sha,
            "size": len(content),
            "content": content,
            "encoding": "utf-8",
        }
        self._in_memory_files[path] = record
        return {
            "content": record,
            "commit": {
                "sha": new_sha,
                "message": message,
            },
        }

    def create_issue_comment(
        self,
        repo: str,
        issue_number: int,
        body: str,
    ) -> Dict[str, Any]:
        """Add a comment to an issue or pull request."""
        return {
            "id": 9901,
            "issue_number": issue_number,
            "body": body,
            "author": "agent-bot",
            "created_at": "2026-10-15T12:00:00Z",
        }

    # -------------------------------------------------------------------------
    # Tool Dictionary Export for Agents
    # -------------------------------------------------------------------------

    def get_tools(self) -> Dict[str, Callable[..., Any]]:
        """Return all standard GitHub tools wrapped with chaos fault injection."""
        return {
            "get_issue": self.wrap_tool("get_issue", self.get_issue),
            "create_issue": self.wrap_tool("create_issue", self.create_issue),
            "create_pull_request": self.wrap_tool("create_pull_request", self.create_pull_request),
            "merge_pull_request": self.wrap_tool("merge_pull_request", self.merge_pull_request),
            "get_file_contents": self.wrap_tool("get_file_contents", self.get_file_contents),
            "update_file": self.wrap_tool("update_file", self.update_file),
            "create_issue_comment": self.wrap_tool("create_issue_comment", self.create_issue_comment),
        }

    def record_audit_event(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        agent_response: str,
        tool_status_code: int = 200,
        tool_succeeded: bool = True,
        tool_output: Optional[Any] = None,
        tool_error: Optional[str] = None,
        injected_fault: Optional[str] = None,
        duration: float = 0.05,
    ) -> UniversalAuditEvent:
        """Record a structured GitHub tool audit event."""
        # Derive verified entities from in-memory state
        verified = []
        for pr_num, pr_data in self._in_memory_prs.items():
            if pr_data.get("merged"):
                verified.append(f"PR#{pr_num}")
                if pr_data.get("merge_commit_sha"):
                    verified.append(pr_data["merge_commit_sha"][:7])
        for iss_num in self._in_memory_issues.keys():
            verified.append(f"#{iss_num}")

        event = UniversalAuditEvent(
            protocol=ProtocolType.GITHUB_API,
            agent_id="github_agent",
            tool_name=tool_name,
            tool_arguments=tool_args,
            injected_fault=injected_fault,
            tool_succeeded=tool_succeeded,
            tool_status_code=tool_status_code,
            tool_output=tool_output,
            tool_error=tool_error,
            agent_response=agent_response,
            duration_seconds=duration,
            channel="github_pr_bot",
            channel_sla_seconds=10.0,
            verified_db_entities=verified,
        )
        self.audit_events.append(event)
        return event
