# Claude Code 与 Coding Agent Harness：28 章图解教程

> 用官方 API 契约、可观察行为与教学用 Harness 解释 Coding Agent；不把未经证实的内部推断写成 Claude Code 源码事实。

**课程入口：** https://1998x-stack.github.io/claude-code-agent-tutorial/

## 学习路线

| 阶段 | 章节 | 说明 |
|---|---|---|
| 第一阶段 | 01–05 | 演进与研究边界、环境、Agent Loop、架构、Tool Use；本轮全篇重构 |
| 第二阶段 | 06–21 | 工具、上下文、子 Agent、权限、Skills、MCP；迁移保留，待事实复审 |
| 第三阶段 | 22–28 | Harness 模式、可观测性、优化与完整系统；迁移保留，待事实复审 |

## 目录

- `site/index.html`：Pages 首页，完整目录无需 JavaScript。
- `site/chapters/01.html` … `28.html`：规范的章节 URL。
- `site/assets/css`：首页、文章设计系统。
- `site/assets/svg`：原创、独立的教学图解。
- `examples/`：可运行样例和单元测试。
- `tools/validate_site.py`：本地与 CI 静态检查。
- `archive/initial/`：第一轮重写前的章节及首页。
- `NN.html` / `site/NN.html`：历史直链兼容跳转。
- `.github/workflows/pages.yml`：将 `site/` 发布到 Pages。

## 运行与发布

```bash
python3 -m http.server 8000
# 浏览 http://localhost:8000/site/
python3 tools/validate_site.py
python3 -m unittest discover -s examples -p 'test_*.py'
```

首次启用 Pages：仓库 Settings → Pages → Build and deployment → Source 选 **GitHub Actions**；推送 main 后工作流会验证并部署 `site/`。不要将存在 workflow 误认为已经发布成功。

## 证据等级与安全

- **官方公开契约**：Claude Code 或 Claude Platform 官方文档和 SDK 公开接口。
- **可观察行为**：有版本与步骤的公开 CLI/API 输入输出。
- **教学设计**：本项目为理解机制而自建的流程、架构、示例代码，不宣称等于 Claude Code 私有源码。
- 不运行模型生成的任意 Shell，不提交密钥；带副作用的工具必须有显式批准与执行边界。

官方参考：[Claude Code docs](https://code.claude.com/docs/en/overview) · [Tool Use docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview)。可视化制作原则参照 [Olah-style-posts](https://github.com/1998x-stack/Olah-style-posts)，仅借鉴渐进解释方法。
