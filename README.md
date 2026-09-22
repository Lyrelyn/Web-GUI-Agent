# Web-GUI-Agent

本地 Web GUI Agent 服务。当前实现至阶段 3：单页 Playwright 闭环、动作效果校验、受限重试、任务取消/总超时，以及 DeepSeek 模型适配器。

## 前置条件

- Windows + Python 3.12+
- [uv](https://docs.astral.sh/uv/)

复制 `.env.example` 为 `.env`，按需调整本地配置。不要将 `.env` 提交到仓库。

若要由真实模型规划动作，在 `.env` 填写 `WEB_GUI_AGENT_DEEPSEEK_API_KEY`；默认使用 DeepSeek OpenAI 兼容地址 `https://api.deepseek.com/v1` 和 `deepseek-chat`。密钥不会写入 API 响应、执行记录或日志。

## 运行与验证

```powershell
uv sync --group dev
uv run playwright install chromium
.\scripts\run.ps1
.\scripts\test.ps1
```

服务仅绑定 `127.0.0.1:8000`。可访问 `GET /healthz`，或通过 `POST /tasks` 创建任务：

```json
{
  "instruction": "在受控页面中搜索示例数据",
  "start_url": "https://example.test/search"
}
```

创建响应中的 `id` 可用于 `GET /tasks/{id}` 查询。阶段 1 使用进程内仓储，因此重启服务会清空任务；持久化将在后续阶段加入。

测试包含受控本地页面的真实 Chromium 流程：导航、填写、选择、点击、提取，再以页面文本证据完成任务。模型的完成说明本身不会令任务成功；必须提供并命中 `expected_text` 页面证据。可恢复的定位、导航超时和模型输出错误只会在任务配置的重试次数内重新观察和规划；取消、总超时与浏览器异常都会关闭任务 Context 并写入一致终态。
