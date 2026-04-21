# schemas (Feature-Aligned Version)

This directory provides schemas aligned with 9 core features, supporting dynamic API integration for Gaode Map and QWeather, with standardized MCP-style tool encapsulation.

## Project Overview

This project delivers a dynamic API integration layer for Gaode Map and QWeather, focusing on standardized, MCP-style (Model Context Protocol) tool encapsulation. The goal is to ensure robust, stable JSON interfaces for LLM Function Calling, with real-time data fetching, field cleaning, and error handling.

## Directory Structure
- `schemas/`: All API interface JSON Schema definitions and feature-to-API mapping
- `.env`: Environment variables (template)
- `README.md`: Project documentation

## Objectives

- Each feature is clearly mapped to a specific API.
- Integrate Gaode Map and QWeather APIs.
- Output fields are deduplicated and cleaned, retaining only decision-critical and troubleshooting fields.
- All APIs are wrapped in an MCP-style tool layer to ensure stable JSON responses for Function Calling by LLMs.

## Relationship with `schemas/`

All schemas are located in the `schemas/` directory. There is no `schemas2/` directory; all tools and extensions are directly maintained in `schemas/` for clarity and ease of integration.

## Contents

1. 12 baseline tools in `schemas/` (same names and structure as legacy contract).
2. 3 additional tools:
   - `tool.gaode.poi_detail.json`
   - `tool.gaode.route_matrix.json`
   - `tool.gaode.traffic_live.json`


## MCP-style Standard Contract

All tools follow a unified top-level structure:

- `ok`
- `request_id`
- `data`
- `error`

With a mutually exclusive `oneOf` constraint:

- Success: `ok=true`, `data=object`, `error=null`
- Failure: `ok=false`, `data=null`, `error=object`

Standard error codes:

- `VALIDATION_ERROR`
- `AUTH_FAILED`
- `RATE_LIMITED`
- `TIMEOUT`
- `UPSTREAM_ERROR`
- `UPSTREAM_EMPTY`

## Field Cleaning Constraints

- `data` only contains fields essential for business decision-making.
- No exposure of undefined or redundant upstream fields.
- Unified troubleshooting passthrough fields are retained:
  - `upstream_status`
  - `upstream_code`
  - `upstream_message`

## Usage

To use this directory at runtime, specify the `schemasDir` as the path to `schemas` when creating the runtime.

## Environment Setup

Create a `.env` file in the project root with the following content:

```env
# Gaode Map API Key
GAODE_API_KEY=your_gaode_api_key_here

# QWeather API Key
QWEATHER_API_KEY=your_qweather_api_key_here
```

## For Data Engineers

As a data engineer, your main responsibilities include:

- Integrating dynamic APIs (Gaode Map, QWeather)
- Cleaning and standardizing response fields
- Encapsulating all logic in MCP-style tool layers
- Ensuring all interfaces are API-First, with stable JSON contracts for downstream consumers (UI, Agent, LLM)
- Supporting real-time data fetching, caching, and anomaly alerts (e.g., instant itinerary adjustment on hotel policy changes)

All tool JSON schemas and the feature-to-API mapping file are now located in the `schemas/` directory. For interface details and mock data, refer to the `schemas/` directory.

## Disaster Recovery & Security Guidelines / 灾难降级与安全规范

### Graceful Degradation & Fallback Protocol / 灾难降级与兜底协议

- **All external API calls (Gaode, QWeather, etc.) must be wrapped in try-catch logic.**
- **A 3-second timeout rule is mandatory:**  
  If any API call times out or fails, the system must silently intercept the error and immediately fall back to local SQLite or AGENTS.md cached/default data.  
  Users should always see a “basic version” of the itinerary or a friendly fallback, never a raw error or stack trace.  
  所有外部 API（高德、飞猪、天气等）调用必须包裹 try-catch 逻辑。
- **三秒兜底原则：**  
  任何 API 超时或报错，系统必须静默拦截，并立刻切换到本地 SQLite 或 AGENTS.md 的默认/历史缓存数据，前端只展示“基础版行程”或友好提示，绝不能让用户看到报错或堆栈。
- **This is a hard requirement for all dynamic toolchain and agent integration code.**  
  Violations will result in critical experience/test deductions.  
  这是所有动态工具链和 Agent 集成代码的硬性要求，违者体验/测试将被严重扣分。

### Security & Compliance / 安全与合规

- **API keys and secrets must never be hardcoded.**  
  Always use environment variables (see `.env` template).  
  API 密钥等敏感信息严禁硬编码，必须通过环境变量管理。
- **All input parameters must be strictly validated according to the schema.**  
  所有入参必须严格按 schema 校验。
- **Do not expose internal error details or sensitive information in any API response.**  
  API 返回中不得暴露内部错误细节或敏感信息。
- **Regularly check and update dependencies for security vulnerabilities.**  
  依赖库需定期安全检查和升级。

### Versioning & Change Management / 版本与变更管理

- **All schema and tool changes must be versioned and documented.**  
  所有 schema 和工具变更必须有版本号和变更记录。
- **Any interface or prompt change must be regression tested with the automated test suite before release.**  
  任何接口或 Prompt 变更，发布前必须跑自动化回归测试。
