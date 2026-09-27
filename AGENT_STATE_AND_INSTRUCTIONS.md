# AgentChaos: Internal Agent State & Continuity Instructions
**Note for AI Assistants / Future Sessions: Read this file FIRST before writing code.**

---

## 1. Project Context & Vision
* **Project Name:** `AgentChaos` (AI Agent Fault Injection & Reliability Testing Framework).
* **Repository Path:** `/home/soumikhandelwal/agent-chaos`
* **Core Philosophy:** Inverting the testing question from *"Does the agent work on the happy path?"* to *"When tools fail, timeout, or act maliciously, does the agent fail safely?"*
* **Architecture Strategy:** Intercept at the **Tool Boundary** (Model-Agnostic, Framework-Agnostic).

### Historical Context & Strategic Decisions (DO NOT REVERSE):
1. **No Salesforce-Only Lock-in:** The original proposal focused on Salesforce Agentforce. We strategically pivoted away because Salesforce already provides native "Agentforce Testing Center".
2. **No Heavy "10k Persona Engine" or "CRM Digital Twins":** Avoid synthetic customer generation and complex database cloning. Focus on lightweight, deterministic, fast tool fault injection and blast-radius assertions.
3. **Open-Source First:** Built for GitHub developers using `pytest`, LangGraph, CrewAI, AutoGen, and Model Context Protocol (MCP).

---

## 2. Project Status & Roadmap

```
[Phase 1: v0.1 Developer Core] ──> COMPLETED (11/11 tests passing, CLI verified)
[Phase 2: v0.2 Universal MCP Chaos Gateway] ──> COMPLETED (21/21 tests passing, CLI stdio proxy verified)
[Phase 3: v0.3 CI/CD & Security Suite] ──> COMPLETED (27/27 tests passing, HTML & JUnit export verified)
[Phase 4: v1.0 Enterprise Governance & Runtime Guard] ──> IN PROGRESS / NEXT UP
```

### Phase 1 (v0.1) Sprint Checklist:
- [x] Market research & product validity validation complete.
- [x] Updated proposal documents: `AI_Agent_Reliability_Platform_Proposal.md` & `.docx`.
- [x] Initialized project directory: `/home/soumikhandelwal/agent-chaos`.
- [x] Created `LEARNING_PATH_AND_DESIGN.md`.
- [x] Created `TESTING_GUIDE.md` (Living catalog and step-by-step test runner instructions).
- [x] Created `AGENT_STATE_AND_INSTRUCTIONS.md`.
- [x] Initialize Python package config (`pyproject.toml` with `setuptools`, editable install verified).
- [x] Implement `agent_chaos/core/faults.py` (Fault specifications: Timeout, HTTPStatus, MalformedJson, Latency).
- [x] Implement `agent_chaos/core/trajectory.py` (In-memory execution tracer & call counter).
- [x] Implement `agent_chaos/core/interceptor.py` (Decorator & context manager for tool wrapping).
- [x] Implement `agent_chaos/core/assertions.py` (Deterministic blast-radius assertions).
- [x] Implement `agent_chaos/adapters/pytest_plugin.py` (Pytest marks and fixtures).
- [x] Add comprehensive test suite in `tests/` verifying all failure modes (11 passed).
- [x] Implement CLI entrypoint (`agent_chaos/cli/main.py`) with `rich` visualizer (`agent-chaos info`, `agent-chaos test`).

### Phase 2 (v0.2) Sprint Checklist:
- [x] Implement `agent_chaos/mcp/` module for Model Context Protocol.
- [x] Implement `agent_chaos/mcp/stdio_proxy.py` (JSON-RPC stdio duplex proxy between MCP client and target server).
- [x] Implement `agent_chaos/mcp/fault_interceptor.py` (Intercepts `tools/call` JSON-RPC method to inject simulated errors).
- [x] Add CLI subcommand: `agent-chaos mcp --target "<cmd>" --fault-tool "<name>" --fault-type "<type>"`.
- [x] Add integration test verifying an MCP server call intercepted with a synthetic error response (21/21 passed).

### Phase 3 (v0.3) Sprint Checklist:
- [x] Implement Automated Red-Teaming / Indirect Prompt Injection Security Suite (`agent_chaos/security/`).
- [x] Built-in adversarial payload bank (`agent_chaos/security/payloads.py`) covering Indirect Injection, System Override, Exfiltration, Privilege Escalation.
- [x] Add CLI subcommand: `agent-chaos redteam --category "<cat>"`.
- [x] Implement GitHub Actions CI/CD template (`.github/workflows/agent-chaos.yml`) for automated PR verification of agent reliability.
- [x] Implement HTML Trajectory Visualizer (`agent_chaos/reporting/html_report.py`) & JUnit XML export (`agent_chaos/reporting/junit_export.py`).
- [x] Comprehensive test coverage with 27 passed tests.

### Phase 4 (v1.0) Sprint Checklist (Next Sprint):
- [ ] Implement Production Circuit Breaker Sidecar (`agent_chaos/guard/`).
- [ ] Implement Live Policy Vault (rate limiting per tool, human-in-the-loop approval gates).
- [ ] Implement Interactive TUI / Live Monitoring Console (`agent-chaos tui`).
- [ ] Compliance & Audit Report Exporter (EU AI Act Article 14 / SOC2 Trust Criteria).

---

## 3. Engineering Invariants & Coding Standards
1. **Python Version:** 3.10+ compatible. Clean, type-hinted code with `mypy`/`pydantic` v2 compatibility.
2. **Deterministic & Lightweight:** Core library must run locally without requiring external servers, API keys, or Docker containers.
3. **Zero-Side-Effect Testing:** Tests must be completely isolated and fast (sub-second execution).
4. **Documentation Rule:** Every time a new module or concept is introduced, update the **Living Code Map** in `LEARNING_PATH_AND_DESIGN.md`.

---

## 4. How to Test & Verify
When working in this repo, run tests using:
```bash
cd /home/soumikhandelwal/agent-chaos
pytest tests/ -v
```
To check code linting/formatting:
```bash
ruff check .
```

---

## 5. Continuity Prompt for Next Session
If picking up this project in a new session:
1. View `/home/soumikhandelwal/agent-chaos/AGENT_STATE_AND_INSTRUCTIONS.md` (this file).
2. Check the **Sprint Checklist** in Section 2 to identify the exact item in progress.
3. Continue directly with implementation without asking redundant setup questions.
