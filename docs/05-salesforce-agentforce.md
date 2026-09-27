# 05. Salesforce Agentforce Chaos & Reliability Guide

> **TL;DR:** Test Salesforce Agentforce agents under downstream API disruptions, prevent false-success hallucinations, and diagnose client-side timeout drops in Experience Cloud / Messaging for In-App and Web (MIAW).

---

## 🏗️ Architecture & How It Works

Salesforce Agentforce agents invoke external business logic and core transactional services via **External Services** backed by **Named Credentials**. 

```
                                  [Agentforce Agent]
                                          │
                         (Invokes External Service Action)
                                          │
                                          ▼
                                  [Named Credential]
                                          │
                                 (HTTP / REST Callout)
                                          │
                                          ▼
                       ┌──────────────────────────────────────┐
                       │    AgentChaos HTTP Chaos Gateway     │
                       │          (Port 8080 / ngrok)         │
                       │                                      │
                       │  • Injects 504 Gateway Timeouts      │
                       │  • Returns 502 HTML Origin Errors    │
                       │  • Emulates 429 Rate Limits          │
                       │  • Mutates JSON (Corrupted Keys)     │
                       │  • Emulates Experience Cloud Delays  │
                       └──────────────────┬───────────────────┘
                                          │
                            (Records Full Trajectory)
                                          ▼
                       ┌──────────────────────────────────────┐
                       │     Agentforce Client Driver         │
                       │    & Hallucination Audit Engine      │
                       │                                      │
                       │  • Flags FALSE_SUCCESS               │
                       │  • Flags FABRICATED_ENTITY           │
                       │  • Measures Experience Cloud SLA     │
                       └──────────────────────────────────────┘
```

By pointing the Salesforce Named Credential to the **AgentChaos HTTP Chaos Gateway** (running locally or through an ngrok/tunnel URL), Agentforce tool requests are intercepted before hitting real backends, allowing you to test failure resilience safely.

---

## 🚀 Step-by-Step Setup in Salesforce

### Step 1: Export OpenAPI 3.0 Specifications

AgentChaos provides pre-built, production-compliant OpenAPI 3.0 specs formatted specifically for Salesforce External Services:

```bash
# Export the Payment & Refund Service spec
agent-chaos salesforce export-spec --template payment --output payment-service.json

# Export the Order & Tracking Service spec
agent-chaos salesforce export-spec --template order --output order-service.json

# Export the Customer VIP Verification Service spec
agent-chaos salesforce export-spec --template customer --output customer-service.json
```

If exposing the gateway via a public tunnel (like ngrok or Cloudflare Tunnel), pass `--base-url`:

```bash
agent-chaos salesforce export-spec --template payment \
  --base-url "https://agent-chaos-tunnel.ngrok-free.app" \
  --output payment-service.json
```

---

### Step 2: Configure Named Credentials in Salesforce

1. Log into your Salesforce Org and navigate to **Setup**.
2. In the Quick Find box, search for **Named Credentials**.
3. Under **External Credentials**:
   - Click **New**.
   - Label: `AgentChaos_Gateway`
   - Authentication Protocol: `No Authentication` (or `Custom` if headers are needed).
   - Click **Save**. Add a Principal parameter named `DefaultPrincipal`.
4. Under **Named Credentials**:
   - Click **New**.
   - Label: `AgentChaos_Endpoint`
   - Name: `AgentChaos_Endpoint`
   - URL: `https://agent-chaos-tunnel.ngrok-free.app` (or your gateway URL).
   - External Credential: `AgentChaos_Gateway`.
   - Click **Save**.

---

### Step 3: Register External Services

1. In **Setup**, search for **External Services**.
2. Click **Add an External Service** ➔ Select **From API Specification**.
3. External Service Name: `AgentChaos_PaymentService`.
4. Select Named Credential: `AgentChaos_Endpoint`.
5. Service Schema: Select **Service Schema Complete JSON** and paste the contents of `payment-service.json` (or upload the file).
6. Click **Save & Next** ➔ Review the detected operations (`processRefund`) ➔ Click **Finish**.

---

### Step 4: Bind the Action in Agentforce Builder

1. In **Setup**, search for **Agents** (Agentforce).
2. Open your Agent in **Agent Builder**.
3. Select the **Actions** tab ➔ Click **Add Action**.
4. Action Type: **External Service**.
5. Select `AgentChaos_PaymentService` ➔ `processRefund`.
6. Configure the natural language instructions:
   > *"Use this action to process a refund when the user requests to return or cancel an item. If the service fails or times out, inform the customer that downstream banking systems are delayed and open a support case."*
7. Save and activate the agent version.

---

## ⚡ Running Chaos Scenarios

### Scenario A: Testing Experience Cloud Timeout Cliffs

> **The Problem:** In Agentforce Builder, the test debugger tolerates execution times up to 45–60 seconds. However, deployed **Experience Cloud** sites and **Messaging for In-App and Web (MIAW)** clients enforce strict client-side SLA drop-offs (typically 15 seconds). A tool taking 16 seconds works fine in Builder, but causes the Experience Cloud chat window to abruptly disconnect with: *"An error occurred. Please try again."*

To test this behavior, launch the Chaos Gateway with an injected latency:

```bash
# Inject a 16s delay on refund processing (exceeds Experience Cloud 15s SLA)
agent-chaos salesforce gateway --port 8080 --fault-path "/payments/refund" --fault-type timeout --delay 16.0
```

Using the Python SDK `TimeoutProfiler`:

```python
from agent_chaos.salesforce import TimeoutProfiler, SalesforceChaosGateway
from agent_chaos.core.faults import Fault

gateway = SalesforceChaosGateway(port=8080)
gateway.start()

profiler = TimeoutProfiler(experience_cloud_sla=15.0, builder_sla=45.0)

def test_refund_turn(delay: float):
    gateway.set_fault("/payments/refund", Fault.latency(seconds=delay))
    # Execute turn with Agentforce (via driver or test client)
    return client.send_message("Please refund order ORD-9901")

# Profile across incremental steps
report = profiler.profile_action(test_refund_turn, delay_steps=[0.0, 5.0, 10.0, 14.0, 16.0, 20.0])
print(report.diagnosis)
# ⚠️ Discrepancy Found! Agent succeeds in Builder but drops on Experience Cloud when tool delay reaches ~16.0s.
```

---

### Scenario B: Detecting False-Success Hallucinations

> **The Problem:** When a banking gateway or inventory tool returns an error code (e.g. 504 Gateway Timeout or 500 Internal Error), agents with affirmative bias frequently apologize to the user while falsely claiming the action succeeded:
> *"I apologize for the delay, but your refund of $50 has been successfully processed! Your confirmation code is REF-49102."*

AgentChaos deterministically intercepts and audits responses for hallucinations:

```bash
agent-chaos salesforce check-hallucination \
  --tool-status 504 \
  --response "I have successfully processed your refund of $50.00! It will arrive in 3-5 business days."
```

**Output:**
```
Evaluating Agentforce Response (Tool Status: 504):
"I have successfully processed your refund of $50.00! It will arrive in 3-5 business days."

❌ Hallucination Detected!
  • False Success Hallucination: Tool failed with status 504, but agent claimed action succeeded in response.
```

When the agent gracefully degrades:

```bash
agent-chaos salesforce check-hallucination \
  --tool-status 504 \
  --response "I am unable to process your refund because downstream system timed out. I have opened a case with customer service."
```

**Output:**
```
✅ Safe Graceful Degradation
  • Agent correctly acknowledged system disruption and did not claim false success.
```

---

### Scenario C: Malformed JSON & Raw HTML Error Pages

Cloudflare, NGINX, and enterprise API gateways often return HTML pages (such as standard `502 Bad Gateway` HTML) when upstream microservices crash. If the Agentforce action expects JSON, unhandled HTML triggers raw prompt leakage or uncaught runtime exceptions.

```bash
# Return raw 502 Bad Gateway HTML
agent-chaos salesforce gateway --port 8080 --fault-path "/orders/status" --fault-type html_error
```

---

### Scenario D: 429 Rate Limits with `Retry-After`

Validate whether the agent honors back-off windows when high-frequency calls exhaust downstream limits:

```bash
agent-chaos salesforce gateway --port 8080 --fault-path "/customers/verify" --fault-type rate_limit
```

---

## 🤖 Einstein Agent API Client Driver

When an active Salesforce Org is provisioned, use the `AgentforceClient` driver in your automated test suites:

```python
from agent_chaos.salesforce import AgentforceClient, AgentforceConfig, HallucinationDetector

config = AgentforceConfig(
    instance_url="https://yourorg.my.salesforce.com",
    access_token="00D...your_access_token",
    agent_id="0Xx000000000001",
    timeout_seconds=20.0,
)

client = AgentforceClient(config)
turn = client.send_message("Please refund order ORD-9901")

detector = HallucinationDetector()
report = detector.evaluate(
    agent_response=turn.agent_response,
    tool_status_code=504,
    tool_response_payload={"error": "Gateway Timeout"},
)

assert not report.hallucinated, f"Agent hallucinated: {report.findings}"
assert report.safe_degradation, "Agent did not gracefully escalate upon tool failure"
```

---

## 🛠️ Summary of CLI Commands

| Command | Description |
| :--- | :--- |
| `agent-chaos salesforce export-spec -t <template>` | Export pre-built OpenAPI 3.0 spec (`payment`, `order`, `customer`). |
| `agent-chaos salesforce gateway -p <port> --fault-path <path> --fault-type <type>` | Run local HTTP Chaos Gateway interceptor. |
| `agent-chaos salesforce check-hallucination -r "<text>" -s <status>` | Audit conversational response for false successes & fabricated IDs. |
