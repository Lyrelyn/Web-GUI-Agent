# Web-GUI-Agent

本地 Web GUI Agent 服务。当前实现阶段 1：任务领域契约、内存任务仓储和本地 HTTP API。

## 前置条件

- Windows + Python 3.12+
- [uv](https://docs.astral.sh/uv/)

复制 `.env.example` 为 `.env`，按需调整本地配置。不要将 `.env` 提交到仓库。

## 运行与验证

```powershell
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
