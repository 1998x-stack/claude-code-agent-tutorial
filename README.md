# Claude Code 与 Coding Agent Harness：28 章图解教程

> 用官方 API 契约、可观察行为与教学用 Harness 解释 Coding Agent；不把未经证实的内部推断写成 Claude Code 源码事实。

**课程入口：** https://1998x-stack.github.io/claude-code-agent-tutorial/  
**课程状态：** 全部 28 章完成精修；每章均有独立 HTML、图示、资料引用和练习。

## 学习路线

| 阶段 | 章节 | 说明 |
|---|---|---|
| 第一阶段 | 01–20 | Agent Loop、Tool Use、工具、Prompt、Sub-Agent、权限、Bash 沙箱、MCP 2026 与 Context Engineering；已精修 |
| 第二阶段 | 21–25 | Skills Runtime、Harness 控制流、Observability、性能工程与生态选型；已精修 |
| 第三阶段 | 26–28 | 长任务与检查点、可审计 Coding Agent、28 章总览与工程验收；已精修 |

## 目录

- `site/index.html`：Pages 首页，完整目录无需 JavaScript。
- `site/chapters/01.html` … `28.html`：规范的章节 URL。
- `site/assets/css`：首页、文章设计系统。
- `site/assets/svg`：原创、独立的教学图解。
- `examples/`：可运行样例和单元测试，包括 Workspace、Prompt、Agent Loop、TaskBoard、Context Budget、Handoff、Sub-Agent Scheduler、Skill Runtime、Completion Gate、Agent Observability、Performance Planner、Ecosystem Review、Long-Running FeatureLedger、Safe Coding Agent，以及权限、沙箱、MCP 与 Context Engineering 示例。
- `tools/validate_site.py`：本地与 CI 静态检查。
- `archive/initial/`：第 01–28 章重写前的原始版本及旧首页。
- `NN.html` / `site/NN.html`：历史直链兼容跳转。
- `.github/workflows/pages.yml`：将 `site/` 发布到 Pages。

## 运行与发布

```bash
python3 -m http.server 8000
# 浏览 http://localhost:8000/site/
python3 tools/validate_site.py
python3 -m unittest discover -s examples -p 'test_*.py'
```

浏览器 QA（工作流运行，需要 Playwright Chromium）：`python3 tools/browser_qa.py --output qa-output`，自动生成页面截图与 JSON 报告。

首次启用 Pages：仓库 Settings → Pages → Build and deployment → Source 选 **GitHub Actions**；推送 main 后工作流会验证并部署 `site/`。不要将存在 workflow 误认为已经发布成功。

## 证据等级与安全

- **官方公开契约**：Claude Code 或 Claude Platform 官方文档和 SDK 公开接口。
- **可观察行为**：有版本与步骤的公开 CLI/API 输入输出。
- **教学设计**：本项目为理解机制而自建的流程、架构、示例代码，不宣称等于 Claude Code 私有源码。
- 不运行模型生成的任意 Shell，不提交密钥；带副作用的工具必须有显式批准与执行边界。

官方参考：[Claude Code docs](https://code.claude.com/docs/en/overview) · [Tool Use docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview)。可视化制作原则参照 [Olah-style-posts](https://github.com/1998x-stack/Olah-style-posts)，仅借鉴渐进解释方法。

## Claude Code 的 AGENTS.md 兼容性

本仓库以 `AGENTS.md` 为跨工具规范，并提供 `CLAUDE.md` 中的 `@AGENTS.md` 导入以兼容使用 Claude Code 的场景。较新的 Claude Code 支持直接读取 `AGENTS.md`，但默认读取策略受到上层 `CLAUDE.md`、用户设置与版本影响；具体请核对[官方记忆文档](https://code.claude.com/docs/en/memory)。

## MCP 协议版本提醒

截至 2026-11，现代 [MCP 2026-07-28 规范](https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning)采用逐请求元数据；旧版 `2025-11-25` 及之前才使用会话级 `initialize`。示例分别测试两种协议时代，不宣称离线报文生成器已经实现完整的 MCP SDK 或网络协议互通。

安全示例不执行模型生成的 Shell。沙箱章节的 `SandboxManifest` 是静态声明预检，不是 OS 沙箱。

## 第 21–25 章：Skills 与 Harness 工程

- 第 21 章遵循 Claude Code 官方 SKILL.md frontmatter 与调用生命周期；离线 catalog 只模拟受限字段，不授予真实工具权限。
- 第 22 章采用公开工作流模式与证据驱动完成契约，不把模型的自然语言“完成”视为任务验收。
- 第 23 章使用 OpenTelemetry 的 Trace/Event/Metric 术语，并默认过滤原始 Prompt、参数和结果正文。
- 第 24 章通过固定任务集比较质量、P95、Token、成本和依赖图并发；不使用过时的固定命中率或模型价格。
- 第 25 章收录官方 SDK、Skills、MCP 与公开开源 Agent，并要求审查 Plugin 的执行权限、网络和数据处理行为。

本批 Python 示例为离线教学代码，不启动真实 Claude Code、模型或 MCP 服务器。

## 第 26–28 章：跨会话到完整交付

- **26 Long-Running Agents**：基于 Anthropic 2025/2026 公开长任务研究讲解初始化与执行会话、独立验收、功能清单、Steering、Kill Switch、状态校验与检查点。离线示例：`examples/long_running_contract.py`。
- **27 Coding Agent 实战**：`examples/safe_coding_agent.py` 使用真实 Messages API 的消息契约，提供可离线运行的三轮 Replay；选择性 Live 模式需本机安装 `anthropic` 并自行配置 API Key。模型只可 ReadFile / ProposeEdit，永不执行 Shell 或应用写入。
- **28 知识图谱与工程验收**：所有章节依赖地图、9 个横切不变量、完整测试/审批/发布门禁和综合实验。

```bash
# 零依赖、无网络、不会把模型补丁写入真实项目
python3 examples/safe_coding_agent.py demo
python3 examples/long_running_contract.py
python3 -m unittest discover -s examples -p 'test_*.py'
python3 tools/validate_site.py
# 可选：在 GitHub Actions 或已安装 Playwright Chromium 的机器上
python3 tools/browser_qa.py --output qa-output
```

**能力边界：** 这是一组教学用 Harness 与安全的只读编程演示，并非可直接部署的通用自主编码平台。真实编辑、Shell、网络/MCP、工作区沙箱与持续执行必须借助独立权限、安全运行时和验收流程。
