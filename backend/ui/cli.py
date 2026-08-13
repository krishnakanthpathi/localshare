"""
Interactive Command Line Interface (CLI Engine) for LocalShare
"""

import sys
import time
import os
import argparse
try:
    from config import state, TCP_PORT, WEB_PORT
    from utils import get_network_interfaces, generate_qr_code_ascii
    from discovery.udp_beacon import UDPDiscoveryServer, discover_peers
    from transfer.server import TCPServerEngine
    from transfer.client import TCPClientEngine
    from sync.clipboard import ClipboardManager
    from ui.web_server import WebServerManager
except ImportError:
    from ..config import state, TCP_PORT, WEB_PORT
    from ..utils import get_network_interfaces, generate_qr_code_ascii
    from ..discovery.udp_beacon import UDPDiscoveryServer, discover_peers
    from ..transfer.server import TCPServerEngine
    from ..transfer.client import TCPClientEngine
    from ..sync.clipboard import ClipboardManager
    from .web_server import WebServerManager

def print_banner(net_info):
    """Print ASCII banner and connection info."""
    print("=" * 64)
    print("  🚀 LocalShare - High-Speed Mesh File & Text Sharing")
    print("=" * 64)
    print(f" 💻 Device Name   : {state.device_name}")
    print(f" 🌐 Primary LAN IP : {net_info['primary']}")
    if net_info.get("tailscale"):
        print(f" 🔒 Tailscale IP   : {net_info['tailscale']}")
    print(f" 📁 Upload Folder : {os.path.abspath(state.upload_dir)}")
    print(f" 📱 Web UI URL    : http://{net_info['primary']}:{WEB_PORT}")
    print("=" * 64)

    # Print ANSI QR code
    web_url = f"http://{net_info['primary']}:{WEB_PORT}"
    print(generate_qr_code_ascii(web_url))
    print("=" * 64)

def run_interactive_server():
    """Launch full node daemon (UDP discovery + TCP server + Web UI + CLI menu)."""
    net_info = get_network_interfaces()
    print_banner(net_info)

    # 1. Start UDP Discovery Server
    udp_server = UDPDiscoveryServer()
    udp_server.start()

    # 2. Start TCP File Server
    tcp_server = TCPServerEngine()
    tcp_server.start()

    # 3. Start Web UI Server
    web_server = WebServerManager(udp_server=udp_server)
    web_server.start()

    print("\n🟢 LocalShare node running. Enter command ('h' for help):")
    
    while True:
        try:
            cmd = input("\nlocalshare > ").strip()
            if not cmd:
                continue

            if cmd in ("h", "help"):
                print("\nAvailable Commands:")
                print("  ls, peers    - List active discovered network peers")
                print("  send         - Interactively select file/directory to send")
                print("  text         - Send text snippet to peers")
                print("  qr           - Show mobile connection QR code")
                print("  config       - View / toggle preferences")
                print("  q, quit      - Stop LocalShare server")

            elif cmd in ("ls", "peers"):
                peers = udp_server.get_active_peers()
                print(f"\n📡 Active Discovered Peers ({len(peers)}):")
                if not peers:
                    print("   No active peers found on local network.")
                for i, p in enumerate(peers, 1):
                    print(f"   {i}. {p['name']} - {p['ip']}:{p['port']} ({p['latency']}ms)")

            elif cmd == "send":
                peers = udp_server.get_active_peers()
                if not peers:
                    target_ip = input("Enter target IP address: ").strip()
                else:
                    print("\nSelect target peer:")
                    for i, p in enumerate(peers, 1):
                        print(f"   {i}. {p['name']} ({p['ip']})")
                    choice = input(f"Select (1-{len(peers)}) or type IP: ").strip()
                    if choice.isdigit() and 1 <= int(choice) <= len(peers):
                        target_ip = peers[int(choice) - 1]["ip"]
                    else:
                        target_ip = choice

                path = input("Enter file or folder path to send: ").strip().strip('"').strip("'")
                if path and target_ip:
                    print(f"📤 Preparing transfer of '{path}' to {target_ip}...")
                    
                    def progress_cb(name, sent, total, speed):
                        pct = (sent / total) * 100 if total > 0 else 0
                        speed_mb = speed / (1024 * 1024)
                        sys.stdout.write(f"\r   Sending {name}: {pct:.1f}% | Speed: {speed_mb:.2f} MB/s  ")
                        sys.stdout.flush()

                    ok, msg = TCPClientEngine.send_path(target_ip, path, progress_callback=progress_cb)
                    print(f"\n   {'✅' if ok else '❌'} {msg}")

            elif cmd == "text":
                text = input("Enter text/snippet to send: ").strip()
                peers = udp_server.get_active_peers()
                if text:
                    count = ClipboardManager.broadcast_text(text, peers)
                    print(f"✅ Text broadcasted to {count} active peer(s).")

            elif cmd == "qr":
                url = f"http://{net_info['primary']}:{WEB_PORT}"
                print(generate_qr_code_ascii(url))

            elif cmd == "config":
                print(f"\n⚙️ Preferences:")
                print(f"   Auto Approve Transfers : {state.auto_approve}")
                print(f"   Upload Directory       : {state.upload_dir}")
                toggle = input("Toggle auto-approve? (y/n): ").strip().lower()
                if toggle == 'y':
                    state.auto_approve = not state.auto_approve
                    print(f"   Auto Approve is now: {state.auto_approve}")

            elif cmd in ("q", "quit", "exit"):
                print("Shutting down LocalShare...")
                udp_server.stop()
                tcp_server.stop()
                web_server.stop()
                break

        except (KeyboardInterrupt, EOFError):
            print("\nShutting down LocalShare...")
            udp_server.stop()
            tcp_server.stop()
            web_server.stop()
            break

def run_cli():
    """Main CLI command parser."""
    parser = argparse.ArgumentParser(description="LocalShare CLI Engine")
    subparsers = parser.add_subparsers(dest="command")

    # Server command
    subparsers.add_parser("server", help="Start LocalShare background server node")

    # Scan command
    subparsers.add_parser("scan", help="Scan LAN for active LocalShare peers")

    # Send command
    send_parser = subparsers.add_parser("send", help="Send file/directory to a peer")
    send_parser.add_argument("path", help="Path to file or folder")
    send_parser.add_argument("--target", help="Target IP address (optional)")

    # Text command
    text_parser = subparsers.add_parser("text", help="Broadcast text snippet")
    text_parser.add_argument("message", help="Text message string")
    text_parser.add_argument("--target", help="Target IP address (optional)")

    args = parser.parse_args()

    if args.command == "scan":
        print("🔍 Scanning LAN for LocalShare devices...")
        peers = discover_peers(timeout=2.0)
        print(f"Found {len(peers)} device(s):")
        for p in peers:
            print(f" - {p['name']} ({p['ip']}:{p['port']}) [{p['latency']}ms]")

    elif args.command == "send":
        target_ip = args.target
        if not target_ip:
            peers = discover_peers(timeout=1.5)
            if peers:
                target_ip = peers[0]["ip"]
                print(f"Auto-selected peer: {peers[0]['name']} ({target_ip})")
            else:
                print("❌ No peers found. Specify --target IP.")
                sys.exit(1)

        ok, msg = TCPClientEngine.send_path(target_ip, args.path)
        print(f"{'✅ Success' if ok else '❌ Error'}: {msg}")

    elif args.command == "text":
        if args.target:
            ok, msg = TCPClientEngine.send_text_snippet(args.target, args.message)
            print(f"{'✅' if ok else '❌'} {msg}")
        else:
            peers = discover_peers(timeout=1.5)
            count = ClipboardManager.broadcast_text(args.message, peers)
            print(f"Broadcasted snippet to {count} peer(s).")

    else:
        # Default action: run interactive server dashboard
        run_interactive_server()
