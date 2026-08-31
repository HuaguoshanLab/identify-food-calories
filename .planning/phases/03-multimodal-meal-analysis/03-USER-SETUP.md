# Phase 3: User Setup Required

**Generated:** 2026-08-31
**Phase:** 03-multimodal-meal-analysis
**Status:** Complete

Qwen-VL 生产配置需要用户拥有的 Alibaba Cloud Model Studio 业务空间。用户已确认以下项目，秘密值未进入 Git：

## Environment Variables

| Status | Variable | Source | Add to |
| --- | --- | --- | --- |
| [x] | `QWEN_API_KEY` | Model Studio → API Key | 未提交的 `backend/.env` |
| [x] | `QWEN_REGION` | 已选华北 2（北京）业务空间 | 未提交的 `backend/.env` |
| [x] | `QWEN_DEPLOYMENT_SCOPE` | 已选默认业务空间 | 未提交的 `backend/.env` |
| [x] | `QWEN_BASE_URL` | Model Studio → API Key → OpenAI compatible Base URL | 未提交的 `backend/.env` |
| [x] | `QWEN_MODEL` | 已核实模型 | 未提交的 `backend/.env` |
| [x] | `QWEN_PRICE_SNAPSHOT_VERSION` 与 `QWEN_UP_TO_*_CNY_PER_M` | 已核实的人民币价格快照 | 未提交的 `backend/.env` |

## Dashboard Configuration

- [x] **核实区域、业务空间和模型可用性**
  - 位置：Alibaba Cloud Model Studio，华北 2（北京）/ 默认业务空间。
  - 模型：`qwen3-vl-flash`。

- [x] **核实图片第三方处理条款**
  - 仅在上述业务空间允许的范围内使用真实图片。
  - 不将 API Key、真实图片或模型响应提交到仓库或测试 fixture。

## Verification

```bash
cd backend
.venv/bin/python -c 'from app.core.config import Settings; from app.providers.vision.factory import create_vision_provider; from app.providers.vision.qwen import QwenVisionModelProvider; assert isinstance(create_vision_provider(Settings()), QwenVisionModelProvider); print("Qwen local configuration: valid")'
```

Expected result: `Qwen local configuration: valid`。这只验证本地配置与 provider 装配，不发送图片或发起付费请求。
