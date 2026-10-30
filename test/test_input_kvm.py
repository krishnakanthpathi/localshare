"""
Unit test for LocalShare Virtual KVM Protocol and Network Roundtrip
"""

import socket
import unittest
from app.input.protocol import (
    MAGIC_BYTE,
    PACKET_SIZE,
    EV_MOVE,
    EV_CLICK,
    EV_SCROLL,
    EV_SWITCH,
    BTN_LEFT,
    BTN_RIGHT,
    pack_packet,
    unpack_packet
)

class TestInputProtocol(unittest.TestCase):
    def test_packet_size(self):
        self.assertEqual(PACKET_SIZE, 6)

    def test_move_pack_unpack(self):
        pkt = pack_packet(EV_MOVE, 12, -45)
        self.assertEqual(len(pkt), 6)
        res = unpack_packet(pkt)
        self.assertIsNotNone(res)
        ev, dx, dy = res
        self.assertEqual(ev, EV_MOVE)
        self.assertEqual(dx, 12)
        self.assertEqual(dy, -45)

    def test_click_pack_unpack(self):
        pkt = pack_packet(EV_CLICK, BTN_RIGHT, 1)
        res = unpack_packet(pkt)
        self.assertIsNotNone(res)
        ev, btn, pressed = res
        self.assertEqual(ev, EV_CLICK)
        self.assertEqual(btn, BTN_RIGHT)
        self.assertEqual(pressed, 1)

    def test_switch_pack_unpack(self):
        pkt = pack_packet(EV_SWITCH, 1, 550)
        res = unpack_packet(pkt)
        self.assertIsNotNone(res)
        ev, mode, norm_y = res
        self.assertEqual(ev, EV_SWITCH)
        self.assertEqual(mode, 1)
        self.assertEqual(norm_y, 550)

    def test_invalid_packet(self):
        self.assertIsNone(unpack_packet(b""))
        self.assertIsNone(unpack_packet(b"12345"))
        self.assertIsNone(unpack_packet(b"\x00\x01\x00\x01\x00\x01"))  # wrong magic

    def test_udp_loopback(self):
        rx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        rx_sock.bind(("127.0.0.1", 0))
        rx_port = rx_sock.getsockname()[1]

        tx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        tx_sock.sendto(pack_packet(EV_MOVE, 88, -22), ("127.0.0.1", rx_port))

        data, _ = rx_sock.recvfrom(64)
        res = unpack_packet(data)
        self.assertEqual(res, (EV_MOVE, 88, -22))

        rx_sock.close()
        tx_sock.close()

if __name__ == "__main__":
    unittest.main()
