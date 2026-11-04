# socratic-mcp

把 Socratic sidecar 包成 **MCP server**：任何支持 MCP 的 agent host（DSH、Claude Desktop、Cursor…）都能直接调用，不需要为每个 host 写插件。

```bash
SOCRATIC_SIDECAR_URL=http://127.0.0.1:8765 python -m socratic_mcp.server
```

## 工具

| 工具 | 作用 |
|---|---|
| `kb_search` | 检索；返回 citation 与页图 URL；可带 `book`+`chapter` 收窄到章回 |
| `kb_read` | 按 chunk_id 读取 |
| `chapter_lookup` | 「卷3」「第7回」或标题片段 → 页码范围与页图；给 `page` 则反查所在章回 |
| `review_session` | 复盘一个教学会话 |
| `socratic_state` | 读教学状态机 |
| `socratic_health` | sidecar 是否可达 + 索引统计 |

## 配置

| 环境变量 | 默认 | 说明 |
|---|---|---|
| `SOCRATIC_SIDECAR_URL` | `http://127.0.0.1:8765` | sidecar 地址 |
| `SOCRATIC_TOKEN` | 空 | 非空时以 `Authorization: Bearer` 发送 |

sidecar 未启动时，工具返回 `{"error":"sidecar_unreachable",...}` 且 `isError: true`，连接不断。

## 挂到 DSH

`~/.dsh/dsh-mcp-plus/servers.json` 加一条：

```json
{
  "mcpServers": {
    "socratic": {
      "command": "python",
      "args": ["-m", "socratic_mcp.server"],
      "env": { "SOCRATIC_SIDECAR_URL": "http://127.0.0.1:8765" }
    }
  }
}
```

## 协议实现范围

`initialize`、`ping`、`tools/list`、`tools/call`，stdio + newline-delimited JSON-RPC 2.0。没有 SDK 依赖（6 条测试，含一次真实 stdio 往返）。
