---
phase: 03-multimodal-meal-analysis
plan: 01
subsystem: image-security-and-provider-boundary
tags: [pillow, image-safety, qwen, provider, pydantic, supply-chain]
requires:
  - phase: 02-agent
    provides: provider ports, fail-closed settings, agent safety conventions
provides:
  - metadata-stripped private temporary image references
  - independently typed and scriptable Vision Provider boundary
  - Pillow 12.3.0 supply-chain evidence and hash-complete lock
affects: [03-02, 03-03, image-upload, qwen-vision]
tech-stack:
  added: [Pillow 12.3.0]
  patterns: [private temporary image repository, provider DTO separation, test-forced fake provider]
key-files:
  created: [backend/app/images/service.py, backend/app/providers/vision/dto.py, backend/app/providers/vision/fake.py]
  modified: [backend/app/core/config.py, backend/requirements.lock, backend/supply-chain-evidence.json]
key-decisions:
  - "图片在 Provider 调用前进行真实解码与重编码，临时引用不含原图或 metadata。"
  - "Pillow 11.3.0 被公开安全信息否决，锁定为 12.3.0。"
patterns-established:
  - "Vision DTO、API schema、ORM 和 Graph State 分离；Provider trace 只含安全计量。"
  - "新增 Python 依赖必须同步更新批准清单、来源证据和 hash-complete lock。"
requirements-completed: [VIS-02, VIS-03, VIS-06]
duration: 55min
completed: 2026-08-31
---

# Phase 3 Plan 01 Summary

**安全图片上传现在先经过有界真实解码、metadata 剥离和私有临时存储，Vision Provider 只能接收最小化引用与严格结构化观察。**

## Accomplishments

- JPEG、PNG、WebP 经过 MIME、字节、像素和真实解码检查后才写入 0700 私有临时目录；引用没有 bytes、base64、原文件名或 EXIF。
- Vision Provider 有独立 Pydantic DTO、窄 Port、test 强制 Fake 和可编排失败类别；Fake trace 不保留图像引用或模型原文。
- 新增 Pillow 12.3.0，完成官方来源证据、供应链门禁和 hash-complete lock 更新。

## Task Commits

1. **Task 1: 建立安全图片临时处理 Service 与最小引用** — `77a135b`
2. **Task 2: 按既有 Provider 模式建立 Vision DTO、Port、Fake 与 Factory** — `9ad1b03`

## Verification

- `backend/.venv/bin/python validate_supply_chain.py verify --schema supply-chain-evidence-v1.schema.json --evidence supply-chain-evidence.json` — PASS
- `backend/.venv/bin/python lock_dependencies.py check --pyproject pyproject.toml --lock requirements.lock` — PASS
- `backend/.venv/bin/python -m pytest tests/unit/test_supply_chain.py tests/unit/test_image_safety.py tests/unit/test_vision_provider.py -q` — 27 passed
- `backend/.venv/bin/python -m mypy app/images app/providers/vision app/core/config.py` — PASS

## Deviations from Plan

Pillow 11.3.0 was replaced with 12.3.0 after current public vulnerability metadata showed fixes only in 12.3.0. This is a required security correction, not scope expansion.

## Next Phase Readiness

Plan 03-02 can implement the Qwen HTTP adapter behind the stable Port. Plan 03-03 can consume `ValidatedImageReference` without exposing raw uploads to the graph.

---
*Phase: 03-multimodal-meal-analysis*
*Completed: 2026-08-31*
