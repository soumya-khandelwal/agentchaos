# Agentforce Chaos & Resilience Studio: Complete Guide

A comprehensive, plain-language guide for Salesforce administrators, architects, and developers to verify, understand, and use the **Agent Chaos Studio** inside Salesforce and from the command line.

---

## 1. What Is This Tool & Why Was It Built?

Salesforce **Agentforce** allows autonomous AI agents to talk directly to your customers and execute real business actions in your Salesforce org (such as creating cases, issuing refunds, or updating orders).

However, autonomous AI agents can fail in ways traditional code never does:
1. **Making false promises:** When a Salesforce validation rule blocks a case from saving, an AI might ignore the error and tell the customer: *"Done! Your case has been created."*
2. **Getting stuck in endless loops:** When an external API fails, the AI might call the same tool 100 times in a row until Salesforce crashes with a governor limit error (`System.LimitException: Too many SOQL queries: 101`).
3. **Crashing on missing information:** If a customer does not provide an email or order number, fragile code crashes with a `NullPointerException` instead of politely asking the customer for the missing details.
4. **Chat timeout cutoffs:** If an action takes longer than 15 seconds, Salesforce's Messaging for In-App and Web (MIAW) drops the chat connection, abandoning the customer.
5. **Inventing fake data:** When searching knowledge bases or Data Cloud returns zero results, the AI might make up fake policies or fake case numbers.

### The Solution: Agent Chaos Studio
**Agent Chaos Studio** is a resilience testing and safety firewall built directly into Salesforce. It lets you:
- **Test your actions under stress** before customers ever talk to your agent.
- **Inject real-world errors** (validation failures, blank inputs, network timeouts) to see if your agent recovers gracefully or breaks.
- **Block dangerous loops automatically** before they burn your Salesforce API and governor limits.
- **Verify everything for free** without spending expensive Salesforce GenAI Flex Credits.

---

## 2. Plain-English Glossary

We avoid confusing developer jargon. Here is how our concepts translate to everyday terms:

| Jargon Term | Plain-English Meaning | Real-World Example |
| :--- | :--- | :--- |
| **Circuit Breaker / Loop Breaker** | **Automatic Safety Stop (Fuse Box)** | If your agent calls the "Create Case" action more than 3 times in a single customer turn, the fuse trips and stops the loop, alerting the customer that a human agent will assist. |
| **ReAct Loop Governor Limit Exhaustion** | **Runaway AI Loop crashing Salesforce** | An AI gets confused and keeps querying the database in an infinite loop until Salesforce hits its hard limit of 100 SOQL queries or 10 seconds of CPU time and crashes. |
| **DML Rollback Blindness** | **Ignoring Save Errors / Falsely Claiming Success** | A Salesforce rule says "Subject cannot be blank". The database rejects the case, but the AI ignores the error and tells the customer: *"Your case #1004 has been logged!"* |
| **Slot-Filling Null Safety** | **Handling Missing or Blank Information** | A customer says *"Create a case"*, omitting their email and description. The code checks for missing values and asks for them instead of crashing with a red error screen. |
| **MIAW Socket Timeout Cliff** | **The 15-Second Chat Cutoff** | Salesforce's web chat (MIAW) automatically terminates the chat session if an agent or action takes longer than 15 seconds to reply. |
| **Data Cloud Grounding Failure** | **Making Up Answers when Knowledge Search is Empty** | When knowledge base search returns 0 results, the agent must say *"I could not find information on that topic"* instead of inventing fake refund policies. |
| **Zero-Credit Simulation** | **Free Offline Testing** | Testing your Apex action handlers and safety guardrails without invoking the LLM model or spending Salesforce GenAI Flex Credits. |

---

## 3. Exact Component Inventory

Here is the exact breakdown of every component used by this tool, divided into **Salesforce Org Components** and **Python Development & Testing Harness**.

```
agent-chaos/
├── force-app/main/default/             <-- SALESFORCE ORG COMPONENTS
│   ├── lwc/agentChaosStudio/          <-- Interactive Tab UI (HTML, JS, CSS)
│   ├── tabs/AgentChaos_Studio.tab     <-- Custom Tab in Salesforce Navigation
│   ├── permissionsets/                <-- AgentChaos_Admin Permission Set
│   ├── objects/Agent_Chaos_Rule__mdt/ <-- Custom Metadata for declarative faults
│   ├── classes/                       <-- Apex Action Gateway & Chaos Engine
│   └── genAiFunctions/ / bots/        <-- Agentforce Agent & Action Definitions
│
└── agent_chaos/                       <-- PYTHON TESTING HARNESS
    ├── salesforce/native/             <-- Action Auditor & SLA Profiler
    ├── salesforce/gateway.py          <-- REST API Connection to Salesforce
    ├── salesforce/hallucination.py    <-- False Promise & Hallucination Detector
    └── cli/main.py                    <-- CI/CD Command Line Tool
```

### A. Salesforce Org Components (Inside Salesforce)

| Component Name | Type | Purpose |
| :--- | :--- | :--- |
| [`agentChaosStudio`](file:///home/soumikhandelwal/agent-chaos/force-app/main/default/lwc/agentChaosStudio/) | Lightning Web Component (LWC) | The visual dashboard tab in Salesforce with live test buttons, progress bar, real-time terminal log, and chat simulator. |
| [`AgentChaos_Studio`](file:///home/soumikhandelwal/agent-chaos/force-app/main/default/tabs/AgentChaos_Studio.tab-meta.xml) | Custom Tab | Exposes the LWC inside standard Salesforce Lightning navigation (`/lightning/n/AgentChaos_Studio`). |
| [`AgentChaos_Admin`](file:///home/soumikhandelwal/agent-chaos/force-app/main/default/permissionsets/AgentChaos_Admin.permissionset-meta.xml) | Permission Set | Grants access to all Chaos Studio Apex controllers, handlers, and Custom Metadata. |
| [`Agent_Chaos_Rule__mdt`](file:///home/soumikhandelwal/agent-chaos/force-app/main/default/objects/Agent_Chaos_Rule__mdt/) | Custom Metadata Type | Stores declarative chaos rules (e.g., inject validation error on `Create_Support_Case_Chaos`). |
| [`AgentChaosStudioController.cls`](file:///home/soumikhandelwal/agent-chaos/force-app/main/default/classes/AgentChaosStudioController.cls) | Apex Controller | The backend engine that feeds data to the LWC, runs the 5-vector resilience tests, and handles chat simulations. |
| [`AgentActionGateway.cls`](file:///home/soumikhandelwal/agent-chaos/force-app/main/default/classes/AgentActionGateway.cls) | Apex Invocable Action | The universal gateway for Agentforce. Inspects every agent action call, checks for runaway loops, and injects chaos faults. |
| [`IAgentActionHandler.cls`](file:///home/soumikhandelwal/agent-chaos/force-app/main/default/classes/IAgentActionHandler.cls) | Apex Interface | The standard contract implemented by all business action handlers (takes input map, returns output map). |
| [`CaseSupportHandler.cls`](file:///home/soumikhandelwal/agent-chaos/force-app/main/default/classes/CaseSupportHandler.cls) | Apex Class | Production handler for creating customer cases with duplicate detection and validation safety. |
| [`AgentChaosEngine.cls`](file:///home/soumikhandelwal/agent-chaos/force-app/main/default/classes/AgentChaosEngine.cls) | Apex Class | Reads Custom Metadata rules and injects configured faults during test runs. |
| [`AgentGatePolicy.cls`](file:///home/soumikhandelwal/agent-chaos/force-app/main/default/classes/AgentGatePolicy.cls) | Apex Class | In-flight safety rules: loop breakers, payload validation, and governor limit monitoring. |
| [`AgentDegradationAdapter.cls`](file:///home/soumikhandelwal/agent-chaos/force-app/main/default/classes/AgentDegradationAdapter.cls) | Apex Class | Generates polite, safe fallback messages for customers when an action encounters an error. |
| [`Customer_Support_Agent`](file:///home/soumikhandelwal/agent-chaos/force-app/main/default/bots/Customer_Support_Agent/) | Agentforce Bot Bundle | Standard Agentforce Service Agent configured to resolve delivery issues and track escalations. |

### B. Python Testing Harness (External / CI/CD)

| Python Class / Script | File Path | Purpose |
| :--- | :--- | :--- |
| `ActionAuditor` | `agent_chaos/salesforce/native/action_auditor.py` | Runs the 5-vector resilience audit programmatically against any Salesforce action handler. |
| `AgentforceGateway` | `agent_chaos/salesforce/gateway.py` | Connects to Salesforce over REST API to execute actions and inspect governor limits. |
| `HallucinationDetector` | `agent_chaos/salesforce/hallucination.py` | Inspects agent replies to ensure it did not invent a fake Case ID or claim success after a database error. |
| `TimeoutProfiler` | `agent_chaos/salesforce/timeout_profiler.py` | Validates that action execution times stay well under channel cutoffs (e.g. 15s for web chat). |
| `CLI Main` | `agent_chaos/cli/main.py` | Command line entry point for running automated audits in GitHub Actions or Jenkins. |

---

## 4. How to Verify from the Frontend (Salesforce UI)

### Step 1: Open the Chaos Studio
1. Log in to Salesforce:
   ```
   https://orgfarm-ed4622b471-dev-ed.develop.my.salesforce.com/lightning/n/AgentChaos_Studio
   ```
2. You will see the **Agentforce Safety Studio** with three clean tabs:
   - **Tab 1: 1. Test an Action**
   - **Tab 2: 2. Live Agent Simulator**
   - **Tab 3: 3. Safety Rules**

---

### Step 2: Test an Action (Tab 1)
1. In **Tab 1: 1. Test an Action**, select an action (e.g. `Create Support Case`).
2. Click **⚡ Run Safety Test**.
3. **What You Will See:**
   - A smooth progress bar running through the safety checks.
   - A clean summary banner:
     ✅ **All 6 Safety Checks Passed** (Action is resilient and safe to deploy).
   - Six bite-sized cards explaining each check in plain English:
     - 🛡️ **Validation Rule & Save Error:** Agent handles save errors honestly without faking success.
     - ❓ **Slot-Filling Fuzz & Null Safety:** Agent asks for missing info instead of crashing with NPE.
     - 👤 **AgentUser Permission Guard:** Gracefully shields permission faults and offers human hand-off.
     - ⚡ **ReAct Loop Breaker:** Fuse automatically trips on 4th repeated tool call.
     - ⏱️ **Front-End Latency Budget:** Response completes within safe CPU limits (~14ms).
     - 🔍 **Data Cloud Grounding:** Empty search results handled without making up fake facts.
   - An optional collapsed link **▶ Show Technical Activity Logs** if you wish to inspect raw backend Apex timestamps.

---

### Step 3: Try the Simulator (Tab 2)
1. Click on **Tab 2: 2. Live Agent Simulator**.
2. Click any of the 3 quick scenario buttons:
   - **📦 Normal Support Request:** Creates a test case cleanly.
   - **⚡ Test Runaway Loop:** Tests how the agent stops after 3 repetitive calls.
   - **❓ Missing Required Info:** Tests how the agent asks for missing details.
3. **What You Will See:**
   - A familiar chat interface with your message on the right (blue) and the agent's response on the left.
   - Under the agent's message, a clean status pill:
     `Action: Create_Support_Case_Chaos • Response Time: 1.25s` (or `👤 Escalated to Human Agent`).

---

### Step 4: Inspect Safety Rules (Tab 3)
1. Click on **Tab 3: 3. Safety Rules**.
2. You will see clean cards showing all active safety protections in your org:
   - **ReAct Loop Breaker:** Limits repeated calls per turn to 3 to prevent governor limit crashes. (🟢 **ACTIVE**)
   - Custom fault rules configured in `Agent_Chaos_Rule__mdt`.
3. To customize or add rules, navigate to **Setup → Custom Code → Custom Metadata Types → Agent Chaos Rule**.

---

## 5. How to Verify from the Backend

### Method A: Salesforce Developer Console (Execute Anonymous Apex)

Open Developer Console (`Debug` > `Open Execute Anonymous Window`) and paste:

```apex
// 1. Run the action reliability audit directly in Apex
AgentChaosStudioController.AuditReport report = 
    AgentChaosStudioController.runActionAudit('CaseSupportHandler');

System.debug('=== CHAOS AUDIT REPORT ===');
System.debug('Overall Resilient: ' + report.isResilient);
System.debug('Score: ' + report.resilienceScore + ' / ' + report.totalVectors);
for (AgentChaosStudioController.VectorResultDTO v : report.results) {
    System.debug(v.name + ': ' + v.status + ' - ' + v.summary);
}
```

**Expected Log Output:**
```
USER_DEBUG|[3]|DEBUG|=== CHAOS AUDIT REPORT ===
USER_DEBUG|[4]|DEBUG|Overall Resilient: true
USER_DEBUG|[5]|DEBUG|Score: 100 / 6
USER_DEBUG|[7]|DEBUG|Validation Rule & DML Rollback Blindness: PASS - Action handled validation rule rollback gracefully and prompted for required fields.
USER_DEBUG|[7]|DEBUG|Slot-Filling Fuzz & Null Safety: PASS - Action handled null arguments without throwing System.NullPointerException.
USER_DEBUG|[7]|DEBUG|AgentUser Permission & Flow Shielding: PASS - Action shielded permission fault gracefully and triggered live human escalation fallback.
USER_DEBUG|[7]|DEBUG|ReAct Loop Breaker & Governor Guard: PASS - Circuit breaker tripped on 4th call, halting runaway token burn and SOQL 101 limit breach.
USER_DEBUG|[7]|DEBUG|Governor CPU & Front-End Latency Budget: PASS - Current transaction CPU time: 14ms (Limit: 10000ms). Synchronous execution within safe budget.
USER_DEBUG|[7]|DEBUG|Data Cloud Grounding & RAG Retrieval: PASS - Empty vector context handled safely without fabricating ungrounded entity IDs or claims.
```

System.debug('Gateway Result: ' + resps[0].isSuccess);
System.debug('Gateway Message: ' + resps[0].responseMessage);
```

**Expected Log Output:**
- `Overall Resilient: true`
- `Score: 5 / 5`
- All 5 vectors marked as `PASS`.

---

### Method B: Salesforce CLI (Terminal)

Run the full Apex test suite using the Salesforce CLI:

```bash
# Run Controller tests
sf apex run test --tests AgentChaosStudioControllerTest --result-format human --target-org agentforce-org

# Run Universal Gateway tests
sf apex run test --tests AgentActionGatewayTest --result-format human --target-org agentforce-org
```

**Expected Output:**
```
=== Test Results
TEST NAME                                                     OUTCOME  MESSAGE  RUNTIME (MS)
────────────────────────────────────────────────────────────  ───────  ───────  ────────────
AgentChaosStudioControllerTest.testAuditActionExecution       Pass              70
AgentChaosStudioControllerTest.testAuditActionWithBlankName   Pass              26
AgentChaosStudioControllerTest.testGetActiveRules             Pass              23
AgentChaosStudioControllerTest.testGetAvailableActions        Pass              42
AgentChaosStudioControllerTest.testGetAvailableAgents         Pass              27
AgentChaosStudioControllerTest.testSimulateAgentTurnVariants  Pass              21
AgentActionGatewayTest.testChaosFaultInjectionBlocked         Pass              35
AgentActionGatewayTest.testDeclarativeMetadataFaultInjection  Pass              14
AgentActionGatewayTest.testHappyPathCaseCreation              Pass              107
AgentActionGatewayTest.testLoopBreakerTripping                Pass              157
AgentActionGatewayTest.testUnknownActionHandling              Pass              16
Outcome: Passed (11/11 tests passing)
```

---

### Method C: SOQL Queries

Verify that cases created during tests are properly logged or rolled back:

```bash
# Query recently created cases
sf data query --query "SELECT Id, CaseNumber, Subject, Priority, Status, CreatedDate FROM Case ORDER BY CreatedDate DESC LIMIT 5" --target-org agentforce-org

# Query Custom Metadata Chaos Rules
sf data query --query "SELECT MasterLabel, Action_Name__c, Fault_Type__c, Is_Active__c FROM Agent_Chaos_Rule__mdt" --target-org agentforce-org
```

---

### Method D: Python Unit Tests & Audit CLI

Run the Python testing harness to verify external audits:

```bash
# Run the 89-test unit suite
pytest tests/ -v

# Run the Salesforce Action Auditor tests specifically
pytest tests/test_action_auditor.py -v
```

**Expected Output:**
```
tests/test_action_auditor.py::test_action_auditor_happy_path_all_vectors_pass PASSED
tests/test_action_auditor.py::test_action_auditor_detects_validation_rule_hallucination PASSED
tests/test_action_auditor.py::test_action_auditor_detects_null_pointer_fuzz_crash PASSED
tests/test_action_auditor.py::test_action_auditor_detects_latency_budget_breach PASSED
tests/test_action_auditor.py::test_action_auditor_detects_data_cloud_grounding_hallucination PASSED
tests/test_action_auditor.py::test_action_auditor_data_cloud_grounding_clean_degradation PASSED
============================== 89 passed in 6.48s ==============================
```

---

## 6. Summary Checklist for Verification

| Item | Frontend (Salesforce UI) | Backend (Apex / CLI) | Status |
| :--- | :--- | :--- | :---: |
| **Audit Execution** | Click button -> Progress Bar & Logs visible | `runActionAudit()` returns 5/5 | ✅ Verified |
| **DML Failure Safety** | Shows honesty badge when save fails | Detects fake Case ID claims | ✅ Verified |
| **Blank Input Fuzzing** | Prompts user for missing field | Handler throws clean error, no NPE | ✅ Verified |
| **Loop Breaker** | Trips fuse on 3+ rapid identical calls | Trip status returned in GatewayResponse | ✅ Verified |
| **Latency Budget** | Response time profiled against 15s MIAW | Latency assertion passes | ✅ Verified |
| **Zero Credit Cost** | Runs offline without spending Flex Credits | All tests execute in local Apex/Python | ✅ Verified |
