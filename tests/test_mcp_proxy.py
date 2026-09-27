"""End-to-end integration tests for MCPChaosProxy."""

import asyncio
import json
import sys
import pytest
from agent_chaos.core.assertions import assert_tool_called
from agent_chaos.core.faults import Fault
from agent_chaos.mcp.fault_interceptor import MCPFaultInterceptor
from agent_chaos.mcp.stdio_proxy import MCPChaosProxy

# Minimal mock MCP server code to run as a subprocess
MOCK_SERVER_SCRIPT = """
import sys, json

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        req = json.loads(line)
    except Exception:
        continue

    req_id = req.get("id")
    method = req.get("method")

    if method == "initialize":
        resp = {"jsonrpc": "2.0", "id": req_id, "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}}}
    elif method == "tools/list":
        resp = {"jsonrpc": "2.0", "id": req_id, "result": {"tools": [{"name": "get_balance"}, {"name": "transfer"}]}}
    elif method == "tools/call":
        name = req.get("params", {}).get("name")
        args = req.get("params", {}).get("arguments", {})
        if name == "get_balance":
            resp = {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": "Balance: $500"}], "isError": False}}
        elif name == "transfer":
            resp = {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": f"Transferred ${args.get('amount')}"}], "isError": False}}
        else:
            resp = {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": "Unknown tool"}], "isError": True}}
    else:
        resp = {"jsonrpc": "2.0", "id": req_id, "result": {}}

    sys.stdout.write(json.dumps(resp) + "\\n")
    sys.stdout.flush()
"""


@pytest.mark.asyncio
async def test_mcp_proxy_interception_and_pass_through():
    interceptor = MCPFaultInterceptor()
    interceptor.set_fault("transfer", Fault.http_error(status_code=500, message="Gateway Timeout"))

    proxy = MCPChaosProxy(
        target_cmd=[sys.executable, "-c", MOCK_SERVER_SCRIPT],
        interceptor=interceptor,
    )

    # Setup simulated client pipes
    client_in_r, client_in_w = await asyncio.open_unix_connection() if hasattr(asyncio, "open_unix_connection_pipe") else await _create_memory_pipe()
    client_out_r, client_out_w = await _create_memory_pipe()

    proxy_task = asyncio.create_task(proxy.run_streams(client_in_r, client_out_w))

    try:
        # 1. Send initialize (should pass through to mock server)
        init_req = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        client_in_w.write(json.dumps(init_req).encode("utf-8") + b"\n")
        await client_in_w.drain()

        resp_line = await asyncio.wait_for(client_out_r.readline(), timeout=3.0)
        init_resp = json.loads(resp_line.decode("utf-8"))
        assert init_resp["id"] == 1
        assert "capabilities" in init_resp["result"]

        # 2. Call non-faulted tool: get_balance (should pass through to mock server)
        bal_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "get_balance", "arguments": {}}}
        client_in_w.write(json.dumps(bal_req).encode("utf-8") + b"\n")
        await client_in_w.drain()

        resp_line = await asyncio.wait_for(client_out_r.readline(), timeout=3.0)
        bal_resp = json.loads(resp_line.decode("utf-8"))
        assert bal_resp["id"] == 2
        assert bal_resp["result"]["content"][0]["text"] == "Balance: $500"
        assert bal_resp["result"]["isError"] is False

        # 3. Call faulted tool: transfer (should be intercepted with synthetic 500 error)
        transfer_req = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "transfer", "arguments": {"amount": 100}},
        }
        client_in_w.write(json.dumps(transfer_req).encode("utf-8") + b"\n")
        await client_in_w.drain()

        resp_line = await asyncio.wait_for(client_out_r.readline(), timeout=3.0)
        transfer_resp = json.loads(resp_line.decode("utf-8"))
        assert transfer_resp["id"] == 3
        assert transfer_resp["result"]["isError"] is True
        assert "500: Gateway Timeout" in transfer_resp["result"]["content"][0]["text"]

        # 4. Verify trajectory recording
        assert_tool_called(proxy.recorder, "get_balance", times=1)
        assert_tool_called(proxy.recorder, "transfer", times=1)
        assert proxy.recorder.has_faulted("transfer")
        assert not proxy.recorder.has_faulted("get_balance")

    finally:
        client_in_w.close()
        try:
            await client_in_w.wait_closed()
        except Exception:
            pass
        proxy_task.cancel()
        try:
            await proxy_task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_mcp_proxy_intermittent_retry_success():
    interceptor = MCPFaultInterceptor()
    # Fails only once
    interceptor.set_fault("transfer", Fault.http_error(status_code=503, message="Temp unavailable", times=1))

    proxy = MCPChaosProxy(
        target_cmd=[sys.executable, "-c", MOCK_SERVER_SCRIPT],
        interceptor=interceptor,
    )

    client_in_r, client_in_w = await _create_memory_pipe()
    client_out_r, client_out_w = await _create_memory_pipe()

    proxy_task = asyncio.create_task(proxy.run_streams(client_in_r, client_out_w))

    try:
        # Call 1: intercepted with 503
        req1 = {"jsonrpc": "2.0", "id": 10, "method": "tools/call", "params": {"name": "transfer", "arguments": {"amount": 50}}}
        client_in_w.write(json.dumps(req1).encode("utf-8") + b"\n")
        await client_in_w.drain()

        resp1 = json.loads((await asyncio.wait_for(client_out_r.readline(), timeout=3.0)).decode("utf-8"))
        assert resp1["result"]["isError"] is True
        assert "503: Temp unavailable" in resp1["result"]["content"][0]["text"]

        # Call 2 (retry): succeeds on the target server
        req2 = {"jsonrpc": "2.0", "id": 11, "method": "tools/call", "params": {"name": "transfer", "arguments": {"amount": 50}}}
        client_in_w.write(json.dumps(req2).encode("utf-8") + b"\n")
        await client_in_w.drain()

        resp2 = json.loads((await asyncio.wait_for(client_out_r.readline(), timeout=3.0)).decode("utf-8"))
        assert resp2["result"]["isError"] is False
        assert resp2["result"]["content"][0]["text"] == "Transferred $50"

        assert_tool_called(proxy.recorder, "transfer", times=2)

    finally:
        client_in_w.close()
        try:
            await client_in_w.wait_closed()
        except Exception:
            pass
        proxy_task.cancel()
        try:
            await proxy_task
        except asyncio.CancelledError:
            pass


async def _create_memory_pipe():
    """Create an in-memory pair of (StreamReader, StreamWriter) connected via an OS pipe."""
    import os
    r_fd, w_fd = os.pipe()

    loop = asyncio.get_running_loop()

    reader = asyncio.StreamReader()
    r_proto = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: r_proto, os.fdopen(r_fd, "rb"))

    w_transport, w_proto = await loop.connect_write_pipe(
        asyncio.streams.FlowControlMixin, os.fdopen(w_fd, "wb")
    )
    writer = asyncio.StreamWriter(w_transport, w_proto, None, loop)

    return reader, writer
