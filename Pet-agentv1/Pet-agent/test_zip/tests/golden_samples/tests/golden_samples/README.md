# Golden Samples for Single-Agent Pre-Trip Evaluation

This folder contains the golden JSON outputs for the **single-agent pre-trip pipeline** of the Pet-agent project. These files are prepared for **Member 3 evaluation on 20 April 2026** and focus on structured, inspectable outputs rather than UI behavior. [file:1215]

## Purpose

The current milestone is to deliver a **single-agent pre-trip planning pipeline**, a **small golden test set**, and the corresponding **saved test outputs** for evaluation. The Apr 20 milestone in the project SOP explicitly requires that the single-agent flow, test set construction, and test result output be completed before the next feedback loop. [file:1215]

These golden files are meant to help check whether the pipeline:
- extracts and normalizes user inputs correctly,
- blocks planning when required information is missing,
- blocks infeasible plans under hard pet-travel constraints,
- packages planner-ready context in a structured JSON format. [file:626]

## Folder contents

Typical files in this folder include:

- `case_001_cn_happy.json`
- `case_002_en_happy.json`
- `case_003_hard_block.json`
- `case_004_missing_fields.json`
- `case_005_fallback_static_only.json`
- `case_006_weather_mock.json`
- `manifest.json`

Some earlier files may also exist as legacy samples, such as `case_001.json`, `case_002.json`, and `case_003.json`. If both old and new versions exist, the files with the clearer names above should be treated as the current canonical set.

## Output schema

Each JSON file is an `evaluation_output` object produced by the single-agent pipeline. It is designed to be easy to inspect and compare across cases.

Core fields include:

- `input_case_id`
- `raw_user_message`
- `input_language`
- `recognized_stage`
- `recognized_task`
- `recognized_field_values`
- `missing_fields_resolution_status`
- `source_provenance`
- `planning_status`
- `planner_result`
- `fallback_or_block_reason`

The pipeline currently standardizes around three planning outcomes:

- `success`
- `blocked_incomplete_context`
- `blocked_hard_constraint`

These outcomes reflect the constraint-driven design in the prompt specification, where the system must avoid fabrication, ask only targeted follow-up questions when information is missing, and stop unsafe or infeasible plans when hard rules are violated. [file:626]

## Case descriptions

### `case_001_cn_happy.json`

Chinese complete pre-trip request with enough information to proceed into planner packaging. This is the main happy-path sample and should produce a planner-ready structured output. If an older version uses `ready_for_planner`, that should be interpreted as equivalent to `success` for the current evaluation set.

### `case_002_en_happy.json`

English complete pre-trip request. This case is intended to check whether the router and planner input packaging still work under English phrasing.

### `case_003_hard_block.json`

Hard-constraint failure case, such as an overweight dog combined with a transport preference that violates the current rule assumptions. This case should produce `blocked_hard_constraint` and no planner result. [file:626][file:1215]

### `case_004_missing_fields.json`

Missing-information case, such as “我想带狗去上海玩”. This case should produce `blocked_incomplete_context` with a targeted follow-up question instead of fabricating a plan. The prompt design explicitly requires only one targeted follow-up question when information is missing. [file:626]

### `case_005_fallback_static_only.json`

Fallback case with missing dynamic travel data. This case is used to verify that the pipeline can still return a safe structured result using static or reduced context, rather than crashing when route or weather details are unavailable. The SOP requires graceful degradation when external APIs are missing or inconsistent. [file:1215]

### `case_006_weather_mock.json`

Weather-sensitive case using mock weather context. This helps inspect whether the planner input carries weather-related planning constraints into downstream reasoning, especially for outdoor-heavy requests. The prompt design explicitly states that long outdoor activities should be prohibited under extreme weather conditions. [file:626]

## Static vs mock data

The current evaluation package uses a mix of **static factual data** and **mock dynamic data**.

### Static data

These sources are treated as stable factual inputs:

- Pet breed/profile databases for cats and dogs, including Purina, AKC, and TICA cleaned datasets. [file:1231]
- Pet travel policy and rule files, including air transport, rail transport, and Beijing/Shanghai urban transit rule JSONs. [file:1231]
- AGENTS.md as the top-level rule framework for default prohibitions, required follow-up, and priority order. [file:1231]

These static sources are meant to serve as the high-confidence constraint layer and fallback knowledge base. The SOP explicitly describes static knowledge and AGENTS.md as the hard fallback when dynamic APIs fail or return incomplete data. [file:1215]

### Mock data

These sources are currently mocked or represented using local sample JSON:

- Weather results (`tool.qweather.*`, Baidu weather examples). [file:1231]
- Route, distance, and POI results from Gaode (`tool.gaode.*`). [file:1231]
- Candidate hotels, pet hospitals, and related dynamic travel resources packaged in local sample tool outputs. [file:1231]

This means the current golden files are designed to validate **logic correctness, blocking behavior, and planner packaging**, not real-time API reliability. The proposal expects real-time APIs eventually, but robust fallback handling is also a core requirement because API data can be fragmented or incomplete. [file:621][file:1215]

## How to regenerate

From the project root, run:

```bash
python app/main.py
```

This should regenerate the evaluation suite and save JSON outputs into this folder.

If `app/main.py` uses:

```python
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "tests" / "golden_samples"
```

then the outputs will be written here regardless of whether the script is launched from the root folder or another working directory.

## What Member 3 should check

Suggested checks for evaluation:

- Whether each case returns a valid structured JSON object.
- Whether `planning_status` matches the expected branch.
- Whether missing-field cases ask for clarification instead of generating a plan.
- Whether hard-constraint cases refuse safely and clearly.
- Whether successful cases include a full `planner_input` with:
  - normalized request,
  - constraint summary,
  - candidate resource summary,
  - evidence blocks,
  - context summary for downstream reasoning. [file:626]

The SOP also emphasizes testing hard-constraint compliance, especially whether the system firmly refuses infeasible pet-travel requests instead of hallucinating alternatives. [file:1215]

## Known limitations

This evaluation package is intentionally limited to the **single-agent pre-trip** phase.

Not fully implemented in this package:

- true 4.1-mini ↔ 5.1-mini dual-model handshake, [file:1215]
- real-time Gaode / Feizhu / weather API integration in the runtime loop, [file:621][file:1231]
- full multi-agent decomposition,
- UI integration,
- trip-companion and post-trip modes. [file:621]

These belong to later phases of the sprint plan and should not be treated as blockers for the Apr 20 single-agent evaluation milestone. [file:1215]

## Notes on legacy files

Earlier golden files such as `case_001.json`, `case_002.json`, and `case_003.json` should be kept temporarily as backups until the new standardized files are confirmed. Once the regenerated files are verified, the old ones can be archived or replaced.

The main normalization change is that older success cases may use:

- `planning_status = "ready_for_planner"`

while the current standardized output uses:

- `planning_status = "success"`

Both indicate the same successful planner handoff intent, but the newer label should be treated as canonical for current evaluation.

## Owner

Prepared by **Member 6 (Agent Engineer A)** for **Member 3 (Evaluation / QA)** as part of the Apr 20 single-agent milestone. [file:1215]