# Learning Path & Design Index

Welcome to AgentChaos. To make reading and learning painless, the documentation has been organized into 4 bite-sized, focused guides in the [`docs/`](docs/) directory:

### 🗺️ The Learning Curriculum

1. [**01. Core Concepts: Why Agents Break**](docs/01-concepts.md)
   * The 3 stages of a tool call
   * The 4 silent failure modes in production agents
   * Why traditional `try/except` doesn't solve agent failure

2. [**02. Architecture & Technical Design**](docs/02-architecture.md)
   * System diagram and component interactions
   * Sequence diagram of the tool interception flow
   * Class reference: `Fault`, `ChaosHarness`, `TrajectoryRecorder`, `Assertions`

3. [**03. Guided Code Walkthrough**](docs/03-code-walkthrough.md)
   * 4-file reading order to understand the repo in 5 minutes
   * 3 hands-on terminal experiments to break things on purpose

4. [**04. Testing Guide & Test Catalog**](docs/04-testing.md)
   * CLI and pytest command cheat sheet
   * Catalog indexing all 11 existing test scenarios
   * Copy-paste template for writing new chaos tests

---
*For internal agent/session continuity instructions, see [`AGENT_STATE_AND_INSTRUCTIONS.md`](AGENT_STATE_AND_INSTRUCTIONS.md).*
