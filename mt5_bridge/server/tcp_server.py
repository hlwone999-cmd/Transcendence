"""TCP server for MT5 EA connections."""

import asyncio
import logging
from typing import Callable, Optional

from ..protocol import (
    Request,
    Response,
    serialize_request,
    parse_response,
    MessageBuffer,
)

logger = logging.getLogger(__name__)

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 1111
READ_TIMEOUT_SECONDS = 1.0
COMMAND_TIMEOUT_SECONDS = 30.0


class MT5Connection:
    """Handles a single MT5 EA connection."""

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ):
        self._reader = reader
        self._writer = writer
        self._buffer = MessageBuffer()
        self._pending_requests: dict[str, asyncio.Future] = {}
        self._connected = True
        self._client_address = writer.get_extra_info("peername")

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def client_address(self) -> tuple:
        return self._client_address

    async def send_request(self, request: Request) -> Response:
        """Send a request and wait for response."""
        if not self._connected:
            raise ConnectionError("Not connected to MT5 EA")

        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_requests[request.request_id] = future

        try:
            data = serialize_request(request)
            self._writer.write(data)
            await self._writer.drain()
            logger.debug(f"Sent request: {request.action.value} [{request.request_id}]")

            response = await asyncio.wait_for(future, timeout=COMMAND_TIMEOUT_SECONDS)
            return response
        except asyncio.TimeoutError:
            logger.error(f"Request timed out: {request.request_id}")
            raise TimeoutError(f"Request {request.action.value} timed out")
        finally:
            self._pending_requests.pop(request.request_id, None)

    async def receive_loop(self) -> None:
        """Continuously read responses from MT5 EA."""
        while self._connected:
            try:
                data = await asyncio.wait_for(
                    self._reader.read(4096),
                    timeout=READ_TIMEOUT_SECONDS
                )
                if not data:
                    logger.info("Connection closed by MT5 EA")
                    self._connected = False
                    break

                self._buffer.append(data)

                while True:
                    message = self._buffer.extract_message()
                    if message is None:
                        break
                    await self._handle_message(message)

            except asyncio.TimeoutError:
                continue
            except Exception as error:
                logger.error(f"Error in receive loop: {error}")
                self._connected = False
                break

        self._cancel_pending_requests()

    async def _handle_message(self, data: bytes) -> None:
        """Process a complete message from MT5 EA."""
        response = parse_response(data)
        if response is None:
            logger.warning("Failed to parse response")
            return

        future = self._pending_requests.get(response.request_id)
        if future and not future.done():
            future.set_result(response)
        else:
            logger.warning(f"Received response for unknown request: {response.request_id}")

    def _cancel_pending_requests(self) -> None:
        """Cancel all pending requests on disconnect."""
        for request_id, future in self._pending_requests.items():
            if not future.done():
                future.set_exception(ConnectionError("Connection lost"))
        self._pending_requests.clear()

    async def close(self) -> None:
        """Close the connection."""
        self._connected = False
        self._writer.close()
        await self._writer.wait_closed()


class MT5Server:
    """TCP server that accepts MT5 EA connections."""

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        on_connect: Optional[Callable[[MT5Connection], None]] = None,
        on_disconnect: Optional[Callable[[MT5Connection], None]] = None
    ):
        self._host = host
        self._port = port
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        self._server: Optional[asyncio.Server] = None
        self._connection: Optional[MT5Connection] = None
        self._receive_task: Optional[asyncio.Task] = None

    @property
    def connection(self) -> Optional[MT5Connection]:
        return self._connection

    @property
    def is_connected(self) -> bool:
        return self._connection is not None and self._connection.is_connected

    async def start(self) -> None:
        """Start the TCP server."""
        self._server = await asyncio.start_server(
            self._handle_client,
            self._host,
            self._port
        )
        logger.info(f"MT5 Server listening on {self._host}:{self._port}")

    async def stop(self) -> None:
        """Stop the server and close connections."""
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        if self._connection:
            await self._connection.close()
            self._connection = None

        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info("MT5 Server stopped")

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ) -> None:
        """Handle a new client connection."""
        if self._connection and self._connection.is_connected:
            logger.warning("Rejecting connection: already connected")
            writer.close()
            await writer.wait_closed()
            return

        connection = MT5Connection(reader, writer)
        self._connection = connection
        logger.info(f"MT5 EA connected from {connection.client_address}")

        if self._on_connect:
            self._on_connect(connection)

        self._receive_task = asyncio.create_task(connection.receive_loop())

        try:
            await self._receive_task
        except asyncio.CancelledError:
            pass
        finally:
            if self._on_disconnect:
                self._on_disconnect(connection)
            self._connection = None
            logger.info("MT5 EA disconnected")

    async def wait_for_connection(self, timeout: float = 60.0) -> MT5Connection:
        """Wait until an MT5 EA connects."""
        start = asyncio.get_event_loop().time()
        while not self.is_connected:
            if asyncio.get_event_loop().time() - start > timeout:
                raise TimeoutError("Timed out waiting for MT5 connection")
            await asyncio.sleep(0.1)
        return self._connection
