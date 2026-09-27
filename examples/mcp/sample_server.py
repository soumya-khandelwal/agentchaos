"""Minimal standalone MCP server demonstrating standard JSON-RPC 2.0 stdio transport."""

import json
import sys


def send_response(req_id, result):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result}) + "\n")
    sys.stdout.flush()


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue

        req_id = msg.get("id")
        method = msg.get("method")

        if method == "initialize":
            send_response(req_id, {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "sample-bank-mcp", "version": "1.0.0"},
                "capabilities": {"tools": {}},
            })
        elif method == "tools/list":
            send_response(req_id, {
                "tools": [
                    {
                        "name": "get_account_balance",
                        "description": "Fetch user balance",
                        "inputSchema": {"type": "object", "properties": {"user_id": {"type": "string"}}},
                    },
                    {
                        "name": "process_refund",
                        "description": "Execute customer refund",
                        "inputSchema": {"type": "object", "properties": {"amount": {"type": "number"}}},
                    },
                ],
            })
        elif method == "tools/call":
            params = msg.get("params", {})
            name = params.get("name")
            args = params.get("arguments", {})

            if name == "get_account_balance":
                send_response(req_id, {
                    "content": [{"type": "text", "text": "Balance: $1,250.00"}],
                    "isError": False,
                })
            elif name == "process_refund":
                send_response(req_id, {
                    "content": [{"type": "text", "text": f"Successfully refunded ${args.get('amount')}"}],
                    "isError": False,
                })
            else:
                send_response(req_id, {
                    "content": [{"type": "text", "text": f"Unknown tool: {name}"}],
                    "isError": True,
                })


if __name__ == "__main__":
    main()
