# 2026-11-23 发布后复审与修复记录

## 复审范围

- 已合并的 main 提交：6ef8fa0c22d66c51fa63e59b91091e215048a357
- 第 26–28 章、三篇对应 SVG、课程首页与 courses.json
- long-running FeatureLedger、CompletionGate、只读 Coding Agent
- HTML/SVG 静态验证、浏览器验收、Pages 与 CI 工作流
- 关键事实对照 Anthropic 与 MCP 官方规范

## 复审发现与修复

| 严重度 | 发现 | 修复 |
|---|---|---|
| 高 | FeatureLedger 对已处于 in_progress 的 feature 再次 start 会重复增加 attempts，恢复会错误耗尽重试预算 | start 对 in_progress 改为幂等恢复；增加 checkpoint resume 回归 |
| 高 | CompletionGate 使用 bool(value)，字符串 "false" 会被当作 True；TaskContract / EvaluatorLoop 接受 bool 作为整数或分数 | 对布尔、整数、有限数值和 artifact 字段做严格类型检查；拒绝拒绝后继续执行 |
| 高 | FeatureLedger 把非空 evidence 字符串当作“已验证证据”，实际不会打开报告或执行测试 | 明确改为 opaque evidence reference；文档声明外部 evaluator 必须先独立核验；代码注释不再夸大保证 |
| 中 | Steering API 仅追加日志，正文却暗示它会直接改变优先级或约束 | 明确它只记录人工备注；真实 Planner 必须消费备注并更新版本化任务契约 |
| 中 | Checkpoint 在读取完整文件后才检查大小，且没有拒绝重复 JSON key | 读取前 stat、实际读取上限、摘要常量时间比较、重复 JSON key 拒绝、schema/字段/类型严格校验 |
| 中 | Coding Agent 以字符数计算 Unicode 文件预算；补丁允许 no-op 和控制字符路径；Malformed / server tool block 缺少明确停止 | 按 UTF-8 字节计量；拒绝 no-op、控制字符路径和 malformed/server-tool blocks；明确停止状态 |
| 中 | 离线 Demo 标题可能让读者误以为调用了真实模型 | 标题与正文明确这是 deterministic Mock，复现 Messages API 结构，不发起模型请求 |
| 中 | 旧静态校验器跳过所有锚点，无法发现失效 TOC、跨页 fragment、courses.json 漂移和 SVG dangling refs | 扩展静态校验：本地文件/fragment、唯一 id、manifest 顺序、28 章清单、SVG title/desc/内部引用 |
| 中 | 浏览器验收虽有 116 视口，但不检查键盘首焦点、章节 TOC 点击、figure caption 与首页所有筛选组 | 增加键盘、TOC、caption、filter 分类、同页 anchor 检查 |
| 低 | 首页目录说明重复同一句 | 删除重复文案 |

## 官方事实复核

- Anthropic 2025-11-26: [Effective harnesses for long-running agents](https://www.anthropic.com/research/effective-harnesses-for-long-running-agents)。Initializer / coding session、feature list、progress journal、Git 与逐 feature 增量工作。
- Anthropic 2026-03-24: [Harness design for long-running application development](https://www.anthropic.com/research/harness-design-long-running-apps)。Planner / Generator / Evaluator 三角色；文章明确区分早期 context reset 与后续同会话自动 compaction 的实验，不应把 reset 描述成所有模型/任务都必需。
- Anthropic Messages API: [Handle tool calls](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)。tool_use id、tool_result 邻接关系、结果字段和并行调用格式。
- Anthropic Messages API: [Stop reasons and fallback](https://platform.claude.com/docs/en/build-with-claude/handling-stop-reasons)。end_turn、max_tokens、stop_sequence、tool_use、pause_turn、refusal 与 model_context_window_exceeded 的语义。
- MCP: [2026-07-28 Specification release](https://blog.modelcontextprotocol.io/posts/2026-07-28/) 与 [Streamable HTTP request metadata](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/basic/transports/streamable-http.mdx)。现代请求版本 header 必须与 params._meta 中 protocolVersion 对齐；clientCapabilities 必须逐请求提供，clientInfo 为 SHOULD。原 AGENTS.md 的描述与规范一致，保留。

## 剩余边界

- actor 字符串仍只是示例标签，绝非安全认证。
- Checkpoint SHA-256 只检测意外篡改；不提供签名、身份、抗恶意文件系统竞态或跨机持久化。
- Workspace 路径检查不是 OS sandbox，不能抵抗 hostile filesystem TOCTOU 或硬链接攻击。
- Messages API 示例只实现 client-side ReadFile / ProposeEdit，不实现 server tools、pause_turn continuation、ApplyPatch、Shell 或部署。
- Playwright QA 是本地静态站点的 Chromium 验收；不替代真实用户设备、屏幕阅读器和所有浏览器测试。

## 验收门禁

```bash
python3 tools/validate_site.py
python3 -m unittest discover -s examples -p 'test_*.py'
python3 tools/browser_qa.py --output qa-output
python3 examples/safe_coding_agent.py demo
python3 examples/long_running_contract.py
python3 examples/completion_gate.py
```

必须以本复审 PR 的 GitHub Actions 实际结果为准，不预先宣称通过。

## 第二轮：早期安全/协议示例复审

### 额外发现
- Workspace 的敏感目录匹配大小写敏感；Windows drive-relative/ADS 路径没有显式拒绝；文件大小仅在 stat 后判断，读取可能因竞态超出预算。
- PermissionPolicy 可被配置成把 Write 放入 safe_reads；approved_by_user 的字符串真值可冒充确认。
- PermissionGateway 的 approved_by 是自由字符串、消费记录只保存在进程内存；之前说明未充分区分“请求指纹匹配”与“真实身份认证”。
- SandboxManifest 接受字符串布尔配置，并且 host/path 检查没有覆盖 Windows 路径和 DNS 名称格式。
- SkillCatalog 支持的 frontmatter 子集会覆盖重复键，supporting file 路径检查没有明确拒绝 Windows drive/backslash。
- MCP envelope 对 bool-as-int、非对象 params 和 JSON NaN/Infinity 的拒绝不够严格。
- HandoffJournal 的加载没有大小上限、重复 JSON key 检查与字段严格校验。

### 修复
- Workspace 增加大小写折叠敏感名、Windows drive/ADS/控制字符拒绝，读取使用有上限的字节流。
- PermissionPolicy 限定 safe_reads 为 Read/Grep；拒绝非 bool 的审批标志。
- PermissionGateway 校验审批字段并在文档中明确身份认证与持久防重放由宿主负责。
- SandboxManifest 严格 bool、DNS/IP 和跨平台路径校验。
- SkillCatalog 拒绝重复 frontmatter 字段并强化 supporting-file 路径与字节上限。
- MCP envelope 严格检查 ID/error code 类型、params 对象和 JSON 有限数值。
- HandoffJournal 增加有界读取、重复键拒绝、schema/字段校验和摘要常量时间比较。

### 明确不提供的安全保证
- Workspace / SkillCatalog 仍可能受同机恶意进程的 TOCTOU 竞态与硬链接影响；不是 OS sandbox。
- PermissionGateway 的 approved_by 不是身份认证；_consumed 仅在进程生命周期内有效。
- SandboxManifest 只是声明预检，不执行命令，也不约束内核。
- Skill frontmatter parser 是受限子集，不是完整 YAML parser。
- Handoff / FeatureLedger 的 SHA-256 不是签名，不能证明写入者身份。
