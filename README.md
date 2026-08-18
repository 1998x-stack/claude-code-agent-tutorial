# ⚡ Claude Code 源码深度解析与 Agent Harness 搭建

> 📘 28章 实战体系 · 交互式 HTML 课程

> **English TL;DR:** An all-Chinese 28-chapter course that **reverse-engineers Claude Code's source and rebuilds a coding-agent harness from scratch**. Alternates deep source teardown (top-level 7-component / 4-layer architecture, Tool-Use protocol, QueryEngine async loop, 5-stage context compaction at 92% threshold, Sub-Agent fork & dirty-context isolation, 7-mode permission system, skills/CLAUDE.md lazy loading, MCP protocol, Context Engineering with 92% prefix-reuse) with hands-on "implement-it-yourself" chapters (minimal agent loop, four basic tools, todo planning, context management, sub-agents, permissions, MCP integration, skills system, full 10-step coding agent). Ends with long-running-agent frontiers (default-FAIL, fresh-context evaluator, kill switch).

## 📖 课程简介

本课程采用「**源码拆解 + 亲手实现**」双线并进的模式：一方面深入 Claude Code 源码——拆解其四大层架构、Tool Use 协议、QueryEngine 主循环、上下文压缩（92% 阈值五级管线）、Sub-Agent fork 机制、权限系统、Skills/CLAUDE.md 懒加载、MCP 集成与 Context Engineering；另一方面以对照章节从零实现最简 Agent Loop、四件套工具、Todo、上下文管理、Sub-Agent、权限控制、Skills 系统与完整 Coding Agent，最后落到 Long-Running Agents 等前沿范式。

## 🚀 快速开始

```bash
open index.html   # macOS，纯静态即开即看
```

## 📂 项目结构

```text
claude-code-agent-tutorial/
├── index.html / 01.html ~ 28.html / courses.json / theme.css
```

## 📖 章节分段

| 轨 | 章节 | 核心 |
|-----|------|------|
| **源码拆解** | 04,06,08 | 顶层架构、Tool Use 协议、QueryEngine 循环 |
| **对照实现** | 03,06,09 | 最小 Agent Loop、四件套工具、Todo |
| **上下文与子 Agent** | 10–13 | 压缩管线、上下文管理、Sub-Agent 分析/实现 |
| **技能与权限** | 14–16 | Skills、权限、MCP |
| **安全与工程** | 17–21 | Bash 沙箱、MCP 集成、Context Engineering、Skills 实现 |
| **模式与实战** | 22–28 | Harness 设计模式、可观测性、性能、趋势、完整 Coding Agent |

## ✨ 亮点

- 唯一「逐行逆向 Claude Code + 从零复刻 Agent Harness」的课程
- 双轨对照：源码篇 vs 实现篇并进
- 覆盖 MCP、权限、上下文工程与 Long-Running Agents 前沿

## 🎯 前置知识

- 适合：Agent Harness 工程师 / 对 Claude Code 好奇的资深开发者
- 建议具备：Python + Prompt/LLM API 经验

## ✨ 特色

- 从逆向到复刻再到前沿，自成 Agent 工程体系
- 即开即用纯静态 HTML

---
*本课程由 `claude-code-agent-tutorial/` 项目维护。*