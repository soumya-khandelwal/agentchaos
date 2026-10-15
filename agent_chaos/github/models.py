"""Data models for GitHub resources, tool schemas, and audit events."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class GitHubIssue(BaseModel):
    """GitHub Issue representation."""
    id: int = 1001
    number: int
    title: str
    body: str
    state: str = "open"
    author: str = "octocat"
    labels: List[str] = Field(default_factory=list)
    created_at: str = "2026-10-15T00:00:00Z"
    comments_count: int = 0


class GitHubPullRequest(BaseModel):
    """GitHub Pull Request representation."""
    id: int = 2001
    number: int
    title: str
    body: str
    state: str = "open"
    base_branch: str = "main"
    head_branch: str = "feature/patch"
    mergeable: bool = True
    merged: bool = False
    merge_commit_sha: Optional[str] = None
    additions: int = 10
    deletions: int = 2
    changed_files: int = 1


class GitHubFileContent(BaseModel):
    """GitHub file content representation."""
    name: str
    path: str
    sha: str = "3b18e512dba79e4c8300dd08aeb37f8e728b8dad"
    size: int = 1200
    content: str = ""
    encoding: str = "utf-8"


class GitHubMergeResult(BaseModel):
    """GitHub PR merge response."""
    sha: str
    merged: bool
    message: str


class GitHubRateLimit(BaseModel):
    """GitHub Rate Limit header representation."""
    limit: int = 5000
    remaining: int = 4999
    reset: int = Field(default_factory=lambda: int(time.time()) + 3600)
    used: int = 1
