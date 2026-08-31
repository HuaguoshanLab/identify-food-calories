---
status: testing
phase: 03-multimodal-meal-analysis
source: 03-01-SUMMARY.md, 03-02-SUMMARY.md, 03-03-SUMMARY.md, 03-04-SUMMARY.md, 03-05-SUMMARY.md
started: 2026-08-31T08:30:39Z
updated: 2026-08-31T08:50:00Z
---

## Current Test

number: 4
name: 不确定或目录外菜不会伪装成完整总量
expected: |
  当页面提示补充份量或出现未匹配菜品时，报告明确提示 partial/未计入或追问，而不会把未知项目静默算作 0 kcal。
awaiting: user retest after fix

## Tests

### 1. 刷新后保持登录与图片报告
expected: 刷新当前分析页后保持登录，已有图片报告仍显示受控菜名、估算重量和非零合计。
result: pass

### 2. 从相册选择图片后得到受控营养报告
expected: 选择一张 JPG、PNG 或 WebP 餐食图并开始分析后，页面展示“估算重量”与逐项/合计营养；识别到目录菜时不显示 0 kcal。
result: pass

### 3. 图片不可用时可切换到文字描述
expected: 点击“改为文字描述这餐”后可输入菜名和克数并得到确定性营养报告，页面不暴露模型原文或内部错误细节。
result: pass

### 4. 不确定或目录外菜不会伪装成完整总量
expected: 当页面提示补充份量或出现未匹配菜品时，报告明确提示 partial/未计入或追问，而不会把未知项目静默算作 0 kcal。
result: pending
previous_issue: 目录外或缺失份量的输入曾显示 0 kcal，容易被误认为完整营养报告。
fix: partial 结果无可计算项目时不再渲染报告卡，改为“无法生成营养报告”；部分可计算结果明确标记为“部分营养报告”。

## Summary

total: 4
passed: 3
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps

- retest-required: `0 kcal` 完整报告缺陷已修复，并由前端回归测试覆盖；等待真实页面复测。
