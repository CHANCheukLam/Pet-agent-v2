# Phase 2 Single-Agent Pre-Trip Core Chain (Fast / Slow Thinking) Handoff

---

## 1. Scope

This handoff documents the **Phase 2 milestone** for the pet-agent project.

The key deliverables completed in this phase are:

- A working **single-agent architecture**.
- A fully connected **fast / slow thinking pipeline**:
  - **Fast layer (4.1-mini equivalent):** intent recognition, stage detection, field extraction, validation, and planner gating.
  - **Slow layer (5.1-mini equivalent):** deep, constraint-aware reasoning, invoked only when the request is complete and safe to plan.
- Deterministic and reproducible evaluation artifacts for review.

The primary goal of Phase 2 is:

> **Correctness, safety, determinism, and evaluability of the agent core loop**  
> rather than UI polish, ranking sophistication, or nationwide feature coverage.

---

## 2. Implemented Capabilities

### 2.1 Single-Agent Pre-Trip Planning Chain

A complete single-agent pre-trip loop is now implemented: [cite:1]

User input  
→ Router (intent recognition, stage detection, field extraction)  
→ Validation and hard-constraint gating  
→ Planner input construction  
→ Deep reasoning entry (5.1-mini equivalent)

The router is intentionally **stateless and conservative**.
The planner is invoked **only** when all required fields are present and hard constraints are satisfied.

### 2.2 Fast / Slow Thinking Switch

The fast / slow thinking handshake is fully operational:

- Simple, incomplete, or informational requests are handled at the router layer.
- Only valid and complete planning requests are forwarded to the planner.
- The planner is never invoked on unsafe or incomplete input.

This ensures that deeper reasoning is used selectively, rather than by default.

### 2.3 Deterministic Terminal Statuses

Each request deterministically resolves to one of the following terminal states:

- `success`
- `blocked_incomplete_context`
- `blocked_hard_constraint`

These statuses are explicit, machine-readable, and consistent across repeated runs.

### 2.4 Golden Evaluation Cases

Six golden test cases are included, with saved JSON outputs under `tests/golden_samples/`:

- Chinese (CN) happy path
- English (EN) happy path
- Hard-constraint block (overweight pet)
- Missing required fields block
- Static-only fallback success
- Weather-constrained success

A consolidated `manifest.json` enumerates all generated results.
All outputs are reproducible from a single command.

---

## 3. Data Usage Model

### 3.1 Static Authoritative Data

The following sources are treated as authoritative and enforced as hard constraints:
- Pet transport and policy rules in `data/static/transport_rules/*`
- Project policy definitions in `AGENTS.md`

These rules are used to determine whether planning is allowed and may block planning entirely.

### 3.2 Static Grounding Data

The system also uses static grounding datasets, including AKC, Purina, and TICA profile data.
These sources support explanation and grounding only; they are **not** used to derive transport or policy rules.

### 3.3 Mock Data Exercised in the Pipeline

The following data sources are currently mocked but actively consumed by the pipeline:

- Weather data (QWeather)
- Maps and routing (Gaode / Amap)
- POIs, hotels, and pet hospitals

These inputs are loaded from deterministic JSON files under `data/mock/`.
They are logically consumed during planner input construction, and planner inputs explicitly annotate provenance as `static` or `mock` to support evaluation and failure attribution. [cite:1]

---

## 4. Phase Boundaries

The following items are intentionally out of scope for Phase 2 and are deferred by design:

- Live external API calls (Gaode / QWeather production endpoints)
- Cross-session persistent memory
- Rich itinerary rendering or UI output
- Multi-option ranking and exploration strategies
- Nationwide or multi-city rule expansion

These are not architectural gaps in the current implementation.
The current design allows them to be added in Phase 3 **without restructuring the agent core loop**.

---

## 5. Evaluation and Reproduction

### 5.1 Evaluation Signals

Each test output includes machine-readable evaluation signals such as:

- `planning_status` — success or block type
- `planner_result != null` — confirms correct planner invocation
- `missing_required_fields` — indicates input completeness
- `blocked_hard_constraint` — confirms enforcement of non-negotiable rules
- Structured planner input — confirms schema completeness

Together, these signals support deterministic review of correctness, routing behavior, and safety enforcement. 

### 5.2 How to Run

**Evaluation mode (default, for reviewers):

```bash
pip install -r requirements.txt
python app/main.py
```

Expected behavior:
- Regenerates all golden samples
- Writes outputs to `tests/golden_samples/`
- Produces `manifest.json`

This is the official evaluation entry point for Phase 2 review.
### 5.3 Optional Agent REPL (Demonstration Mode)

For interactive demonstration, the agent also supports an optional REPL mode:

```bash
python app/main.py --repl
```

This mode enables:

- Interactive pre-trip dialogue in both single-turn and multi-turn formats
- Explicit per-session memory persistence
- Use of the same router and planner logic as the evaluation pipeline
- Demonstration without modifying golden test outputs

The REPL is intended for showcasing agent behavior and multi-turn interaction flow. It is not the official evaluation entry point and does not replace deterministic batch evaluation.