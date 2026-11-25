# Claude Code 与 Coding Agent Harness：28 章图解教程

> 用官方 API 契约、可观察行为与教学用 Harness 解释 Coding Agent；不把未经证实的内部推断写成 Claude Code 源码事实。

**课程入口：** https://1998x-stack.github.io/claude-code-agent-tutorial/

## 学习路线

| 阶段 | 章节 | 说明 |
|---|---|---|
| 第一阶段 | 01–20 | Agent Loop、Tool Use、工具、Prompt、Sub-Agent、权限、Bash 沙箱、MCP 2026 与 Context Engineering；已精修 |
| 第二阶段 | 21–22 | Skills 按需加载与预算截断、Harness 完成模式；已按公开证据重写 |
| 第三阶段 | 23–28 | 可观测性、性能、生态筛选、长任务、集成装配与总结；已完成事实复核与图示重构 |

## 目录

- `site/index.html`：Pages 首页，完整目录无需 JavaScript。
- `site/chapters/01.html` … `28.html`：规范的章节 URL。
- `site/assets/css`：首页、文章设计系统。
- `site/assets/svg`：原创、独立的教学图解。
- `examples/`：可运行样例和单元测试，包括 Workspace、Prompt、Agent Loop、TaskBoard、Context Budget、Handoff、Sub-Agent Scheduler、Skills Catalog、Permission Policy、Permission Gateway、Sandbox Manifest、MCP 双版本报文/注册中心与 Context Tuning。
- `tools/validate_site.py`：本地与 CI 静态检查。
- `archive/initial/`：第 01–20 章重写前的原始版本及旧首页。
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
