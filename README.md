# Cursor ACP 虚拟终端

基于 ACP 协议的命令行终端，无 TUI 刷屏，支持颜色和 diff 显示。

## 特性

- **无 TUI 刷屏** - 纯流式输出，支持 tmux/screen
- **颜色支持** - ANSI 颜色区分不同类型的输出
- **Diff 显示** - 类似 `git diff` 的文件修改预览
- **自动权限** - 自动处理工具调用权限请求

### 输出颜色说明

| 颜色 | 含义 |
|------|------|
| 青色 | AI 回复内容 |
| 灰色斜体 | AI 思考过程 |
| 绿色 `+` | 新增的代码行 |
| 红色 `-` | 删除的代码行 |
| 黄色 | 工具调用/文件修改 |
| 洋红色 | 命令执行结果 |

## 使用

```bash
python3 acp_terminal.py
```

输入 `exit`、`quit` 或 `q` 退出。

## 工作原理

程序通过 ACP 协议与 Cursor Agent 通信：

1. 启动 `agent acp` 进程
2. 通过 JSON-RPC 发送/接收消息
3. 解析 `session/update` 中的不同消息类型：
   - `agent_thought_chunk` - AI 思考（灰色）
   - `agent_message_chunk` - AI 回复（青色）
   - `tool_call` - 工具调用开始
   - `tool_call_update` - 工具调用结果（包含 diff）

## 容器环境

在 docs-desiner CLI 容器中使用时：
- 容器已配置为 `coder` 用户运行
- `CURSOR_API_KEY` 环境变量对 ACP 模式无效，脚本会自动清理
- 认证凭据存储在 `~/.cursor/cli-config.json`

## 要求

- Python 3.6+（无外部依赖）
- Cursor CLI (`agent`) 已安装并登录
