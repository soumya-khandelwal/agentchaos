"""Interactive client demonstrating AgentChaos MCP Gateway interception."""

import json
import subprocess
import sys
import time
from rich.console import Console
from rich.panel import Panel

console = Console()


def run_demo():
    console.print(Panel.fit(
        "[bold cyan]AgentChaos MCP Gateway Live Demonstration[/bold cyan]\n"
        "[dim]Testing transparent tool fault injection on a live MCP server over stdio[/dim]",
        border_style="cyan",
    ))

    cmd = [
        sys.executable, "-m", "agent_chaos.cli.main", "mcp",
        "--target", f"{sys.executable} examples/mcp/sample_server.py",
        "--fault-tool", "process_refund",
        "--fault-type", "http_error",
        "--status-code", "504",
        "--message", "Gateway Timeout: Payment core bank ledger unreachable",
    ]

    console.print(f"[bold yellow]Spawning Proxy:[/bold yellow] [green]{' '.join(cmd)}[/green]\n")

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    def send_and_recv(title: str, req: dict):
        console.print(f"[bold]{title}[/bold]")
        console.print(f"[dim]Client -> Proxy:[/dim] {json.dumps(req)}")
        proc.stdin.write(json.dumps(req) + "\n")
        proc.stdin.flush()

        resp_line = proc.stdout.readline()
        resp = json.loads(resp_line)
        is_err = resp.get("result", {}).get("isError", False)
        color = "red" if is_err else "green"
        console.print(f"[dim]Proxy -> Client:[/dim] [{color}]{json.dumps(resp, indent=2)}[/{color}]\n")
        time.sleep(0.5)

    try:
        # Step 1: Handshake
        send_and_recv(
            "1️⃣  Initialize Handshake (Passes through to target)",
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        )

        # Step 2: List available tools
        send_and_recv(
            "2️⃣  Discover Tools (Passes through to target)",
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        )

        # Step 3: Call get_account_balance (Unfaulted tool)
        send_and_recv(
            "3️⃣  Call Unfaulted Tool: 'get_account_balance' (Normal execution on target)",
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "get_account_balance", "arguments": {"user_id": "u_99"}}},
        )

        # Step 4: Call process_refund (Faulted tool)
        send_and_recv(
            "4️⃣  Call Targeted Tool: 'process_refund' (💥 Intercepted by AgentChaos!)",
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "process_refund", "arguments": {"amount": 250}}},
        )

        console.print("[bold green]✅ Demonstration Complete![/bold green] Notice how 'process_refund' was intercepted with synthetic 504 error without ever executing on the real server.")

    finally:
        proc.stdin.close()
        proc.terminate()
        proc.wait()


if __name__ == "__main__":
    run_demo()
