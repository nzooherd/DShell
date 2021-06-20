# -*- coding: utf-8 -*-
# @Time    : 6/19/2021 4:57 PM
# @Author  : nzooherd
# @File    : shell_protocol.py
# @Software: PyCharm
import asyncio
import subprocess
import logging

from random import randint
from typing import Tuple, List
from collections import defaultdict

from shell_struct import ShellRequest, ShellResponse, parse_data, ShellStructFlag

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class ShellProtocol(asyncio.DatagramProtocol):

    lock = asyncio.Lock()
    stdout = None

    def __init__(self):
        self._outstanding = {}
        self.transport = None
        self.endpoint2buffer = defaultdict(lambda :{})
        self.endpoints: List[Tuple[str, int]] = [("127.0.0.1", 1234), ("127.0.0.1", 1235)]

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport

    def datagram_received(self, data: bytes, endpoint: Tuple[str, int]) -> None:
        shell_struct = parse_data(data)
        if isinstance(shell_struct, ShellRequest):
            asyncio.ensure_future(self.handle_request(shell_struct, endpoint))
        elif isinstance(shell_struct, ShellResponse):
            asyncio.ensure_future(self.handle_response(shell_struct, endpoint))

    async def handle_request(self, shell_request: ShellRequest, endpoint: Tuple[str, int]):
        """
        the client will process the command and return the response
        """
        command = ShellProtocol.data2content(shell_request.data)
        logger.debug("Receive ShellRequest: %s from %s" % (command, endpoint))
        await self.process_shell_command(command, shell_request.request_id, endpoint)

    async def handle_response(self, shell_response: ShellResponse, endpoint: Tuple[str, int]):
        """
        the server will handle response
        """
        request_id = shell_response.request_id
        message_seq = shell_response.message_seq
        content = ShellProtocol.data2content(shell_response.data)
        logger.debug("Receive ShellResponse: %s from %s" % (content, endpoint))

        self.endpoint2buffer[endpoint][message_seq] = content

        if shell_response.get_flag(ShellStructFlag.IS_FINISH):
            async with ShellProtocol.lock:
                print("%s >>>:" % (endpoint, ))
                content_buffer  = self.endpoint2buffer[endpoint]
                for i in range(0, message_seq+1):
                    ShellProtocol.shell_print(content_buffer.get(i))
                future = self._outstanding[(request_id, endpoint)]
                future.set_result(True)
                ShellProtocol.stdout = None

    async def execute_command(self, command):
        request_id = randint(0, 0x7fffffff)
        shell_request = ShellRequest.build_request(request_id, ShellProtocol.content2data(command))
        loop = asyncio.get_event_loop()
        for endpoint in self.endpoints:
            self.transport.sendto(shell_request.to_datagram(), endpoint)
            future = loop.create_future()
            self._outstanding[(request_id, endpoint)] = future

        await asyncio.gather(*self._outstanding.values())

    async def process_shell_command(self, command: str, request_id: int, endpoint: Tuple[str, int]):
        fy_process = subprocess.Popen(command.split(), stdout=subprocess.PIPE)
        message_seq = 0
        while True:
            output = fy_process.stdout.readline()
            if fy_process.poll() is not None and output == b'':
                break
            if output:
                line = output.decode("utf-8")
                shell_response = ShellResponse.\
                    build_response(message_seq=message_seq, request_id=request_id, data=ShellProtocol.content2data(line))
                self.transport.sendto(shell_response.to_datagram(), endpoint)
                message_seq += 1

        shell_response = ShellResponse. \
            build_response(message_seq=message_seq, request_id=request_id, data=ShellProtocol.content2data("\n"), is_finish=True)
        self.transport.sendto(shell_response.to_datagram(), endpoint)

    @staticmethod
    def content2data(content: str) -> bytes:
        return content.encode("utf-8")

    @staticmethod
    def data2content(data: bytes) -> str:
        return data.decode("utf-8")

    @staticmethod
    def shell_print(content: str):
        if content:
            print(content, end="")
