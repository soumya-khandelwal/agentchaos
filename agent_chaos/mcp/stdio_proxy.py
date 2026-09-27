"""MCP stdio proxy for duplex JSON-RPC communication and fault injection."""

from __future__ import annotations

import asyncio
import json
import logging
import shlex
import sys
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from agent_chaos.core.trajectory import TrajectoryRecorder
from agent_chaos.mcp.fault_interceptor import MCPFaultInterceptor, MCPInterceptorResult

logger = logging.getLogger("agent_chaos.mcp.proxy")


class MCPChaosProxy:
    """Duplex stdio proxy running between an MCP Client and an MCP Server."""

    def __init__(
        self,
        target_cmd: Union[str, List[str]],
        interceptor: Optional[MCPFaultInterceptor] = None,
        recorder: Optional[TrajectoryRecorder] = None,
    ) -> None:
        self.target_cmd = target_cmd
        self.recorder = recorder or (interceptor.recorder if interceptor else TrajectoryRecorder())
        self.interceptor = interceptor or MCPFaultInterceptor(recorder=self.recorder)
        self.process: Optional[asyncio.subprocess.Process] = None
        self._pending_calls: Dict[Union[int, str], Tuple[str, Dict[str, Any], float, Optional[Any]]] = {}
        self._running = False
        self._client_write_lock = asyncio.Lock()
        self._server_write_lock = asyncio.Lock()

    async def start_server_process(self) -> asyncio.subprocess.Process:
        """Start the target MCP server subprocess."""
        if isinstance(self.target_cmd, str):
            cmd_args = shlex.split(self.target_cmd)
        else:
            cmd_args = list(self.target_cmd)

        proc = await asyncio.create_subprocess_exec(
            *cmd_args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self.process = proc
        return proc

    async def run_streams(
        self,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
    ) -> None:
        """Run proxy duplex loops between given client streams and target server."""
        proc = await self.start_server_process()
        self._running = True

        client_to_server_task = asyncio.create_task(
            self._handle_client_to_server(client_reader, client_writer, proc)
        )
        server_to_client_task = asyncio.create_task(
            self._handle_server_to_client(client_writer, proc)
        )
        server_stderr_task = asyncio.create_task(
            self._handle_server_stderr(proc)
        )

        try:
            # Wait until either the client disconnects or the server exits
            done, pending = await asyncio.wait(
                [client_to_server_task, server_to_client_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for t in pending:
                t.cancel()
        finally:
            self._running = False
            server_stderr_task.cancel()
            await self._cleanup()

    async def _handle_client_to_server(
        self,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        proc: asyncio.subprocess.Process,
    ) -> None:
        """Read incoming JSON-RPC from client, intercept if needed, or forward to server."""
        while self._running:
            line = await client_reader.readline()
            if not line:
                break  # Client closed connection (EOF)

            stripped = line.strip()
            if not stripped:
                continue

            try:
                msg = json.loads(stripped.decode("utf-8"))
            except Exception:
                # Not valid JSON, forward directly
                await self._write_to_server(proc, line)
                continue

            if isinstance(msg, dict):
                interception = self.interceptor.process_request(msg)
                if interception.intercepted:
                    if interception.delay > 0:
                        await asyncio.sleep(interception.delay)

                    if interception.pass_through_after_delay:
                        # Latency fault: delay completed, now forward to target server
                        req_id = msg.get("id")
                        if req_id is not None:
                            params = msg.get("params") or {}
                            self._pending_calls[req_id] = (
                                interception.tool_name or "",
                                params.get("arguments") or {},
                                time.perf_counter(),
                                interception.fault_type,
                            )
                        await self._write_to_server(proc, line)
                    else:
                        # Synthetic fault response generated
                        resp_bytes = json.dumps(interception.response_payload).encode("utf-8") + b"\n"
                        await self._write_to_client(client_writer, resp_bytes)
                    continue

                # Not intercepted: track tool call if applicable
                if msg.get("method") == "tools/call":
                    req_id = msg.get("id")
                    if req_id is not None:
                        params = msg.get("params") or {}
                        self._pending_calls[req_id] = (
                            params.get("name") or "",
                            params.get("arguments") or {},
                            time.perf_counter(),
                            None,
                        )

            await self._write_to_server(proc, line)

    async def _handle_server_to_client(
        self,
        client_writer: asyncio.StreamWriter,
        proc: asyncio.subprocess.Process,
    ) -> None:
        """Read stdout from server, record pass-through trajectories, and forward to client."""
        assert proc.stdout is not None
        while self._running:
            line = await proc.stdout.readline()
            if not line:
                break  # Server process stdout closed

            stripped = line.strip()
            if stripped:
                try:
                    resp = json.loads(stripped.decode("utf-8"))
                    if isinstance(resp, dict) and "id" in resp:
                        req_id = resp["id"]
                        if req_id in self._pending_calls:
                            tool_name, args, start_time, fault_injected = self._pending_calls.pop(req_id)
                            duration_ms = (time.perf_counter() - start_time) * 1000
                            err_str = None
                            if "error" in resp:
                                err_str = str(resp["error"])
                            elif isinstance(resp.get("result"), dict) and resp["result"].get("isError"):
                                err_str = "MCP Tool Error"

                            self.interceptor.record_pass_through(
                                tool_name=tool_name,
                                arguments=args,
                                duration_ms=duration_ms,
                                result=resp.get("result"),
                                error=err_str,
                                fault_injected=fault_injected,
                            )
                except Exception:
                    pass

            await self._write_to_client(client_writer, line)

    async def _handle_server_stderr(self, proc: asyncio.subprocess.Process) -> None:
        """Forward server stderr to sys.stderr for diagnostic logging."""
        assert proc.stderr is not None
        while self._running:
            line = await proc.stderr.readline()
            if not line:
                break
            try:
                sys.stderr.buffer.write(line)
                sys.stderr.buffer.flush()
            except Exception:
                pass

    async def _write_to_client(self, writer: asyncio.StreamWriter, data: bytes) -> None:
        async with self._client_write_lock:
            writer.write(data)
            await writer.drain()

    async def _write_to_server(self, proc: asyncio.subprocess.Process, data: bytes) -> None:
        if proc.stdin and not proc.stdin.is_closing():
            async with self._server_write_lock:
                proc.stdin.write(data)
                await proc.stdin.drain()

    async def _cleanup(self) -> None:
        """Terminate target server process and close resources."""
        if self.process:
            if self.process.stdin and not self.process.stdin.is_closing():
                try:
                    self.process.stdin.close()
                except Exception:
                    pass
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=2.0)
            except (asyncio.TimeoutError, ProcessLookupError):
                try:
                    self.process.kill()
                except Exception:
                    pass

    async def run_stdio(self) -> None:
        """Connect to current process's standard input and output streams."""
        loop = asyncio.get_running_loop()

        # Connect async reader to stdin
        reader = asyncio.StreamReader()
        reader_proto = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: reader_proto, sys.stdin.buffer)

        # Connect async writer to stdout
        w_transport, w_proto = await loop.connect_write_pipe(
            asyncio.streams.FlowControlMixin, sys.stdout.buffer
        )
        writer = asyncio.StreamWriter(w_transport, w_proto, reader, loop)

        await self.run_streams(reader, writer)
