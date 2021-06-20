# -*- coding: utf-8 -*-
# @Time    : 6/19/2021 4:34 PM
# @Author  : nzooherd
# @File    : shell_struct.py
# @Software: PyCharm
from enum import Enum

MAGIC_NUMBER = b"\xDC\xCE"

class ShellStructFlag(Enum):
    IS_REQUEST = 0
    IS_FINISH = 1

    @staticmethod
    def build_flags(is_request=False, is_finish=False) -> str:
        origin_flags = [0] * 8
        if is_request:
            origin_flags[ShellStructFlag.IS_REQUEST.value] = 1
        if is_finish:
            origin_flags[ShellStructFlag.IS_FINISH.value] = 1
        return "".join(['1' if flag else '0' for flag in origin_flags])

    @staticmethod
    def to_bytes(flags: str) -> bytes:
        return bytes([int(flags, 2)])

class ShellStruct:
    """
    protocol "Magic Number:16, Flag:8, MessageSeq:8, RequestId:32"
     0                   1                   2                   3
     0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |          Magic Number         |      Flag     |   MessageSeq  |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |                            RequestId                          |
    -+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    """

    def __init__(self, flags: str, message_seq: int, request_id: int, data: bytes):
        self.flags = flags
        self.message_seq = message_seq
        self.request_id = request_id
        self.data = data

    def get_flag(self, flag: ShellStructFlag) -> bool:
        return self.flags[flag.value] == '1'

    @classmethod
    def from_datagram(cls, datagram: bytes):
        if len(datagram) < 8:
            raise Exception("Illegal Datagram")

        magic_number = datagram[0:2]
        if magic_number != MAGIC_NUMBER:
            raise Exception("Illegal Magic Number")

        flags = "{:08b}".format(int(datagram[2:3].hex(), 16))
        message_seq = datagram[3]
        request_id = int(datagram[4:8].hex(), 16)
        data = datagram[8:]
        return cls(flags, message_seq, request_id, data)

    def to_datagram(self) -> bytes:
        return MAGIC_NUMBER +  ShellStructFlag.to_bytes(self.flags) + \
               bytes([self.message_seq]) + self.request_id.to_bytes(4, byteorder='big') + self.data

class ShellRequest(ShellStruct):

    def __init__(self, shell_struct: ShellStruct):
        super().__init__(shell_struct.flags, shell_struct.message_seq, shell_struct.request_id, shell_struct.data)

    @classmethod
    def build_request(cls, request_id: int, data: bytes):
        return ShellRequest(
            ShellStruct(ShellStructFlag.build_flags(is_request=True, is_finish=True), 1, request_id, data))


class ShellResponse(ShellStruct):

    def __init__(self, shell_struct: ShellStruct):
        super().__init__(shell_struct.flags, shell_struct.message_seq, shell_struct.request_id, shell_struct.data)

    @classmethod
    def build_response(cls, message_seq: int,  request_id: int, data: bytes, is_finish=False):
        flags = ShellStructFlag.build_flags(is_request=False, is_finish=is_finish)
        return ShellResponse(ShellStruct(flags, message_seq, request_id, data))

def parse_data(datagram: bytes) -> ShellStruct:
    shell_struct = ShellStruct.from_datagram(datagram)
    if shell_struct.get_flag(ShellStructFlag.IS_REQUEST):
        return ShellRequest(shell_struct)
    else:
        return ShellResponse(shell_struct)
