# 01. Core Concepts: Why Agents Break

> **TL;DR:** When LLMs interact with external tools (APIs, databases), traditional error handling fails. Agents don't crash gracefully; they hallucinate fake success, get stuck in infinite retry loops, or call unauthorized fallback tools.

---

## The 3 Stages of an Agent Tool Call

```text
User Dialogue --> [ 1. Model Thinks ] --> Generates Tool Call JSON
                                                |
                                                v
Real World    <-- [ 3. Model Synthesizes ] <-- [ 2. Tool Executes ]
```

1. **Reasoning:** Model parses user intent and outputs tool arguments:
   `process_refund(order_id="ORD-101", amount=750)`
2. **Execution:** Your backend executes the function. What if the network fails or returns `504 Timeout`?
3. **Synthesis:** Model receives the error message and decides what to do next.

---

## The 4 Silent Killers in Production

| Failure Mode | What Actually Happens | Real-World Impact |
| :--- | :--- | :--- |
| **1. Fake Success** | Tool fails, but agent tells customer: *"Done! Refund sent."* | Customer confusion, chargebacks, broken trust. |
| **2. Infinite Retry Loop** | Tool returns `429 Rate Limit`. Agent retries 20 times in a row. | Database hammered, token bill spikes by $50+. |
| **3. Dangerous Fallback** | Read-only tool fails; agent tries an unauthorized write tool. | Data corruption or unintended state mutations. |
| **4. Data Poisoning** | Tool returns text containing indirect prompt injection. | Agent hijacked to leak credentials or bypass policy. |

---

## Why `try / except` Isn't Enough

Traditional code testing checks:
> *"Does my Python function throw an unhandled exception?"*

Agent testing must check:
> ***"When my Python function throws an error, how does the AI model react to that error in its next action?"***

AgentChaos tests this behavioral boundary.

---

[Next: 02. Architecture & Technical Design →](02-architecture.md)
