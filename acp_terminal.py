#!/usr/bin/env python3
"""
Cursor ACP 虚拟终端
基于 ACP 协议，无 TUI 刷屏，支持颜色和 diff 显示
"""
import difflib
import json
import os
import subprocess
import sys


# ═══════════════════════════════════════════════════════════════════════════════
# ANSI 颜色
# ═══════════════════════════════════════════════════════════════════════════════

class C:
    """ANSI 颜色代码"""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    GRAY = "\033[90m"
    
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"

# 检测是否支持颜色
_COLOR_ENABLED = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()

def c(color: str, text: str) -> str:
    """给文本添加颜色"""
    if _COLOR_ENABLED:
        return f"{color}{text}{C.RESET}"
    return text


# ═══════════════════════════════════════════════════════════════════════════════
# Diff 渲染
# ═══════════════════════════════════════════════════════════════════════════════

def render_diff(path: str, old_text: str, new_text: str) -> str:
    """渲染 diff 输出，类似 git diff"""
    lines = []
    
    # 文件路径标题
    if old_text is None:
        lines.append(c(C.GREEN + C.BOLD, f"[NEW] {path}"))
    else:
        lines.append(c(C.YELLOW + C.BOLD, f"[MOD] {path}"))
    
    # 如果是新文件，直接显示内容
    if old_text is None:
        for line in new_text.split('\n'):
            lines.append(c(C.GREEN, f"+ {line}"))
        return '\n'.join(lines)
    
    # 计算 diff
    old_lines = old_text.split('\n')
    new_lines = new_text.split('\n')
    
    differ = difflib.unified_diff(old_lines, new_lines, lineterm='', n=3)
    
    for i, line in enumerate(differ):
        if i < 2:  # 跳过 --- 和 +++ 行
            continue
        if line.startswith('@@'):
            lines.append(c(C.CYAN, line))
        elif line.startswith('-'):
            lines.append(c(C.RED, line))
        elif line.startswith('+'):
            lines.append(c(C.GREEN, line))
        else:
            lines.append(c(C.GRAY, line))
    
    return '\n'.join(lines) if lines else c(C.GRAY, "(无变化)")


def render_command_output(title: str, exit_code: int, stdout: str, stderr: str) -> str:
    """渲染命令执行输出"""
    lines = []
    
    # 命令标题
    status = c(C.GREEN, "✓") if exit_code == 0 else c(C.RED, "✗")
    lines.append(f"{status} {c(C.MAGENTA + C.BOLD, title)}")
    
    # 输出内容
    if stdout:
        for line in stdout.rstrip().split('\n'):
            lines.append(c(C.GRAY, f"  {line}"))
    
    if stderr:
        for line in stderr.rstrip().split('\n'):
            lines.append(c(C.RED, f"  {line}"))
    
    return '\n'.join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# 主程序
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    cwd = os.getcwd()
    
    # 查找 agent 路径
    agent_path = "/home/coder/.local/bin/agent" if os.path.exists("/home/coder/.local/bin/agent") else "agent"
    cmd = [agent_path, "acp"]
    
    # 清理环境变量：CURSOR_API_KEY 对 acp 模式无效
    env = os.environ.copy()
    env.pop("CURSOR_API_KEY", None)
    
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        cwd=cwd,
        env=env,
    )

    def send(method, params):
        send.rid += 1
        msg = {"jsonrpc": "2.0", "id": send.rid, "method": method, "params": params}
        proc.stdin.write((json.dumps(msg) + "\n").encode())
        proc.stdin.flush()
        return send.rid
    send.rid = 0

    def recv():
        line = proc.stdout.readline().decode().strip()
        return json.loads(line) if line else None

    def req(method, params):
        send(method, params)
        r = recv()
        if not r or "error" in r:
            raise RuntimeError(r.get("error", "无响应") if r else "无响应")
        return r.get("result", {})

    # 启动界面
    print(c(C.CYAN + C.BOLD, "╔═══════════════════════════════════════╗"))
    print(c(C.CYAN + C.BOLD, "║") + "     Cursor ACP 虚拟终端              " + c(C.CYAN + C.BOLD, "║"))
    print(c(C.CYAN + C.BOLD, "╚═══════════════════════════════════════╝"))
    print(c(C.GRAY, "输入 exit/quit/q 退出\n"))
    
    try:
        req("initialize", {"protocolVersion": 1, "clientCapabilities": {}, "clientInfo": {"name": "acp-terminal", "version": "2.0"}})
        r = req("session/new", {"cwd": cwd, "mcpServers": []})
        sid = r["sessionId"]
        print(c(C.GREEN, "✓ 已连接") + f" [{c(C.YELLOW, sid[:8])}...]\n")
    except Exception as e:
        print(c(C.RED, f"✗ 连接失败: {e}"))
        print(c(C.GRAY, "请确认已通过 'agent login' 登录"))
        proc.terminate()
        return

    # 跟踪工具调用
    tool_calls = {}

    while True:
        try:
            text = input(c(C.GREEN + C.BOLD, "> "))
        except (EOFError, KeyboardInterrupt):
            break
        if not text.strip():
            continue
        if text.strip().lower() in ("exit", "quit", "q"):
            break
        
        rid = send("session/prompt", {"sessionId": sid, "prompt": [{"type": "text", "text": text}]})
        print()
        
        # 用于累积思考内容
        thinking_buffer = ""
        message_buffer = ""
        
        while True:
            line = proc.stdout.readline()
            if not line:
                break
            
            m = json.loads(line.decode())
            
            if m.get("method") == "session/update":
                update = m.get("params", {}).get("update", {})
                session_update = update.get("sessionUpdate", "")
                
                # AI 思考过程（灰色、斜体）
                if session_update == "agent_thought_chunk":
                    t = update.get("content", {}).get("text", "")
                    if t:
                        thinking_buffer += t
                        print(c(C.GRAY + C.ITALIC, t), end="", flush=True)
                
                # AI 回复内容
                elif session_update == "agent_message_chunk":
                    t = update.get("content", {}).get("text", "")
                    if t:
                        # 如果刚从思考切换到消息，换行
                        if thinking_buffer and not message_buffer:
                            print()
                        message_buffer += t
                        print(c(C.CYAN, t), end="", flush=True)
                
                # 工具调用开始
                elif session_update == "tool_call":
                    tool_id = update.get("toolCallId", "")
                    title = update.get("title", "")
                    kind = update.get("kind", "")
                    status = update.get("status", "")
                    
                    tool_calls[tool_id] = {
                        "title": title,
                        "kind": kind,
                        "status": status,
                    }
                    
                    # 显示工具调用
                    if status == "pending" and title:
                        icon = "[EDIT]" if kind == "edit" else "[RUN]" if kind == "execute" else "[TOOL]"
                        print(f"\n{c(C.MAGENTA, icon)} {c(C.YELLOW, title)}", flush=True)
                
                # 工具调用更新/完成
                elif session_update == "tool_call_update":
                    tool_id = update.get("toolCallId", "")
                    status = update.get("status", "")
                    
                    if tool_id in tool_calls:
                        tool_calls[tool_id]["status"] = status
                    
                    # 处理完成的工具调用
                    if status == "completed":
                        content = update.get("content", [])
                        raw_output = update.get("rawOutput", {})
                        
                        # diff 类型（文件编辑）
                        for item in content:
                            if item.get("type") == "diff":
                                diff_output = render_diff(
                                    item.get("path", ""),
                                    item.get("oldText"),
                                    item.get("newText", "")
                                )
                                print(diff_output, flush=True)
                        
                        # 命令执行结果
                        if raw_output and "exitCode" in raw_output:
                            title = tool_calls.get(tool_id, {}).get("title", "命令")
                            cmd_output = render_command_output(
                                title,
                                raw_output.get("exitCode", 0),
                                raw_output.get("stdout", ""),
                                raw_output.get("stderr", "")
                            )
                            print(cmd_output, flush=True)
            
            # 自动处理权限请求
            elif m.get("method") == "session/request_permission":
                proc.stdin.write((json.dumps({
                    "jsonrpc": "2.0",
                    "id": m["id"],
                    "result": {"outcome": {"outcome": "selected", "optionId": "allow-once"}}
                }) + "\n").encode())
                proc.stdin.flush()
            
            # 响应完成
            elif m.get("id") == rid:
                break
        
        print()
        thinking_buffer = ""
        message_buffer = ""

    proc.terminate()
    proc.wait()
    print(c(C.GRAY, "\n再见"))


if __name__ == "__main__":
    main()
