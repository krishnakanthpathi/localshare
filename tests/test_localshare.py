"""
Comprehensive Automated Unit & Integration Tests for LocalShare System (FastAPI & FastMCP)
"""

import unittest
import os
import shutil
import tempfile
import time
import json
import socket
from fastapi.testclient import TestClient

from localshare.config import state
from localshare.utils import get_network_interfaces, sanitize_relative_path, safe_join, is_suspicious_file
from localshare.transfer.protocol import send_message, receive_message
from localshare.transfer.server import TCPServerEngine
from localshare.transfer.client import TCPClientEngine
from localshare.ui.web_server import app
from localshare.mcp_service.mcp_server import localshare_discover_peers, localshare_toggle_approval

class TestLocalShare(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.upload_dir = os.path.join(self.test_dir, "uploads")
        os.makedirs(self.upload_dir, exist_ok=True)
        state.upload_dir = self.upload_dir
        state.auto_approve = True

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_network_interfaces(self):
        net_info = get_network_interfaces()
        self.assertIn("primary", net_info)
        self.assertIn("all", net_info)
        self.assertTrue(len(net_info["all"]) >= 1)

    def test_security_sanitization(self):
        # Path traversal prevention tests
        bad_path = "../../etc/passwd"
        clean = sanitize_relative_path(bad_path)
        self.assertNotIn("..", clean)
        self.assertEqual(clean, "etc/passwd")

        # safe_join test
        joined = safe_join(self.upload_dir, "../../secret.txt")
        self.assertTrue(joined.startswith(os.path.abspath(self.upload_dir)))

        # Suspicious extension check
        self.assertTrue(is_suspicious_file("malware.exe"))
        self.assertTrue(is_suspicious_file("script.sh"))
        self.assertFalse(is_suspicious_file("document.pdf"))

    def test_protocol_framing(self):
        # Test socket message framing
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.bind(("127.0.0.1", 0))
        port = server_sock.getsockname()[1]
        server_sock.listen(1)

        client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_sock.connect(("127.0.0.1", port))
        conn, _ = server_sock.accept()

        test_data = {"type": "TEST", "value": 12345, "msg": "Hello LocalShare"}
        send_message(client_sock, test_data)
        recv_data = receive_message(conn)

        self.assertEqual(test_data, recv_data)

        client_sock.close()
        conn.close()
        server_sock.close()

    def test_end_to_end_file_transfer(self):
        # Test full TCP file transfer from client to server
        server = TCPServerEngine(port=4500)
        server.start()
        time.sleep(0.2)

        # Create dummy source file
        src_file = os.path.join(self.test_dir, "sample.txt")
        content = "Hello, LocalShare networking lab! " * 100
        with open(src_file, "w") as f:
            f.write(content)

        # Send file
        ok, msg = TCPClientEngine.send_path("127.0.0.1", src_file, target_port=4500)
        self.assertTrue(ok, f"Transfer failed: {msg}")

        # Check file received on server
        rcv_file = os.path.join(self.upload_dir, "sample.txt")
        self.assertTrue(os.path.exists(rcv_file), "Received file does not exist")
        
        with open(rcv_file, "r") as f:
            rcv_content = f.read()
        self.assertEqual(content, rcv_content)

        server.stop()

    def test_directory_tree_transfer(self):
        # Test transferring a full directory structure
        server = TCPServerEngine(port=4501)
        server.start()
        time.sleep(0.2)

        # Create nested directory structure
        src_dir = os.path.join(self.test_dir, "my_folder")
        sub_dir = os.path.join(src_dir, "nested_sub")
        os.makedirs(sub_dir, exist_ok=True)

        with open(os.path.join(src_dir, "root.txt"), "w") as f:
            f.write("root file content")
        with open(os.path.join(sub_dir, "child.txt"), "w") as f:
            f.write("nested child content")

        ok, msg = TCPClientEngine.send_path("127.0.0.1", src_dir, target_port=4501)
        self.assertTrue(ok)

        # Verify folder tree structure saved in upload_dir
        self.assertTrue(os.path.exists(os.path.join(self.upload_dir, "my_folder", "root.txt")))
        self.assertTrue(os.path.exists(os.path.join(self.upload_dir, "my_folder", "nested_sub", "child.txt")))

        server.stop()

    def test_fastapi_web_endpoints(self):
        client = TestClient(app)

        # Test GET /api/config
        res = client.get("/api/config")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["auto_approve"], True)
        self.assertIn("web_url", data)

        # Test GET /api/qrcode
        res_qr = client.get("/api/qrcode")
        self.assertEqual(res_qr.status_code, 200)
        self.assertIn("<svg", res_qr.text)

    def test_mcp_tool_execution(self):
        res = localshare_toggle_approval(auto_approve=False)
        self.assertEqual(res["status"], "success")
        self.assertEqual(state.auto_approve, False)

        res_discover = localshare_discover_peers(timeout=0.5)
        self.assertEqual(res_discover["status"], "success")
        self.assertIn("peers", res_discover)

if __name__ == "__main__":
    unittest.main()
