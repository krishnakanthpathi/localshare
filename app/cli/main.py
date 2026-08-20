"""
Interactive Command Line Interface (CLI Engine) for LocalShare
Rich terminal dashboard, multi-folder batch queuing, MongoDB settings manager, and Tailscale peer resolver.
"""

import sys
import os
import time
import argparse
from app.config import state, TCP_PORT, WEB_PORT, DEFAULT_UPLOAD_DIR
from app.utils import get_network_interfaces, generate_qr_code_ascii
from app.db.mongo import (
    load_settings, save_settings, get_settings_dict,
    get_peer_alias, set_peer_alias, delete_peer_alias, get_all_peer_aliases,
    is_connected as is_mongo_connected
)
from app.security.encryption import generate_key, encrypt_text, decrypt_text
from app.discovery.udp_beacon import UDPDiscoveryServer, discover_peers
from app.discovery.tailscale import get_tailscale_peers, get_tailscale_status
from app.queue.manager import queue_manager
from app.queue.models import TransferStatus
from app.transfer.server import start_tcp_server, stop_tcp_server
from app.transfer.client import send_single_file, send_batch, send_text_snippet
from app.sync.clipboard import get_system_clipboard, set_system_clipboard, broadcast_text
from app.api.server import start_web_server

def format_bytes(size_bytes: int) -> str:
    """Format bytes into readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

def print_banner():
    """Print ASCII banner and live node connection info."""
    net_info = get_network_interfaces()
    mongo_ok = is_mongo_connected()

    print("\n" + "=" * 68)
    print("  🚀 LOCALSHARE 2.0 - High-Speed Encrypted Mesh File Transfer")
    print("=" * 68)
    print(f" 💻 Device Name   : {state.device_name}")
    print(f" 🌐 Primary LAN IP : {net_info['primary']} (Port: {TCP_PORT})")
    if net_info.get("tailscale"):
        print(f" 🔒 Tailscale IP   : {net_info['tailscale']} [Active]")
    print(f" 🍃 MongoDB Status : {'🟢 Connected' if mongo_ok else '🟡 Offline (In-Memory Cache)'}")
    print(f" 🔐 Encryption     : {'🟢 AES-256-GCM Active' if state.encryption_enabled and state.encryption_key else '⚪ Disabled'}")
    print(f" ⚡ Compression    : {'🟢 Gzip (Level ' + str(state.compression_level) + ')' if state.compression_enabled else '⚪ Disabled'}")
    print(f" 📁 Upload Folder : {os.path.abspath(state.upload_dir)}")
    print("=" * 68)

def show_settings_panel():
    """Interactive Settings & Preferences Manager."""
    while True:
        mongo_ok = is_mongo_connected()
        print("\n" + "-" * 50)
        print("         ⚙️  SETTINGS & PREFERENCES PANEL")
        print("-" * 50)
        print(f" 1. Device Name          : {state.device_name}")
        print(f" 2. Upload Directory     : {state.upload_dir}")
        print(f" 3. Auto-Approve Files   : {'✅ Enabled' if state.auto_approve else '❌ Prompt Required'}")
        print(f" 4. Gzip Compression    : {'✅ Enabled (Level ' + str(state.compression_level) + ')' if state.compression_enabled else '❌ Disabled'}")
        print(f" 5. AES-256 Encryption   : {'✅ Enabled' if state.encryption_enabled else '❌ Disabled'}")
        print(f" 6. Encryption Key       : {state.encryption_key[:12] + '...' if state.encryption_key else '<Not Set>'}")
        print(f" 7. MongoDB Connection   : {state.mongo_uri} ({'🟢 Online' if mongo_ok else '🔴 Offline'})")
        print(f" 8. Back to Main Menu")
        print("-" * 50)

        choice = input("Select setting to modify (1-8): ").strip()

        if choice == "1":
            new_name = input(f"Enter new device name [{state.device_name}]: ").strip()
            if new_name:
                save_settings({"device_name": new_name})
                print(f"✅ Device name updated to '{state.device_name}'")

        elif choice == "2":
            new_dir = input(f"Enter upload directory path [{state.upload_dir}]: ").strip().strip('"').strip("'")
            if new_dir:
                abs_dir = os.path.abspath(os.path.expanduser(new_dir))
                os.makedirs(abs_dir, exist_ok=True)
                save_settings({"upload_dir": abs_dir})
                print(f"✅ Upload directory set to: {state.upload_dir}")

        elif choice == "3":
            new_val = not state.auto_approve
            save_settings({"auto_approve": new_val})
            print(f"✅ Auto-approve is now {'ENABLED' if state.auto_approve else 'DISABLED'}")

        elif choice == "4":
            toggle = input(f"Toggle Gzip compression? (currently {'ON' if state.compression_enabled else 'OFF'}) (y/n): ").strip().lower()
            if toggle == "y":
                new_state = not state.compression_enabled
                save_settings({"compression_enabled": new_state})
                print(f"✅ Compression is now {'ENABLED' if state.compression_enabled else 'DISABLED'}")
            
            if state.compression_enabled:
                lvl = input("Set compression level (1=Fastest, 6=Balanced, 9=Max) [default 6]: ").strip()
                if lvl.isdigit() and 1 <= int(lvl) <= 9:
                    save_settings({"compression_level": int(lvl)})
                    print(f"✅ Compression level set to {state.compression_level}")

        elif choice == "5":
            if not state.encryption_key and not state.encryption_enabled:
                print("⚠️ No encryption key set. Generating a new AES-256 key...")
                new_k = generate_key()
                save_settings({"encryption_key": new_k, "encryption_enabled": True})
                print(f"✅ Generated new AES Key: {new_k}")
            else:
                new_state = not state.encryption_enabled
                save_settings({"encryption_enabled": new_state})
            print(f"✅ Encryption is now {'ENABLED' if state.encryption_enabled else 'DISABLED'}")

        elif choice == "6":
            print("\nKey Management:")
            print(" a) Generate a new random AES-256 key")
            print(" b) Enter key manually or use custom passphrase")
            print(" c) Clear encryption key")
            opt = input("Choose option (a/b/c): ").strip().lower()
            if opt == "a":
                k = generate_key()
                save_settings({"encryption_key": k, "encryption_enabled": True})
                print(f"✅ Generated & Saved new AES-256 Key: {k}")
            elif opt == "b":
                k = input("Enter 32-byte Base64 key or passphrase: ").strip()
                if k:
                    save_settings({"encryption_key": k, "encryption_enabled": True})
                    print("✅ Encryption key updated and enabled.")
            elif opt == "c":
                save_settings({"encryption_key": "", "encryption_enabled": False})
                print("✅ Encryption key cleared.")

        elif choice == "7":
            new_uri = input(f"Enter MongoDB connection URI [{state.mongo_uri}]: ").strip()
            if new_uri:
                save_settings({"mongo_uri": new_uri})
                if is_mongo_connected():
                    print("🟢 Successfully connected to MongoDB!")
                else:
                    print("⚠️ Could not connect to MongoDB at that URI. Saved for retry.")

        elif choice == "8" or choice.lower() in ("b", "q", "exit"):
            break

def manage_peer_aliases():
    """Interactive Peer Name & Alias Manager."""
    while True:
        aliases = get_all_peer_aliases()
        print("\n" + "-" * 55)
        print("        🏷️  PEER NAME & IP ALIAS MANAGER (MongoDB)")
        print("-" * 55)
        if not aliases:
            print("  No custom peer aliases configured yet.")
        else:
            for i, (ip, data) in enumerate(aliases.items(), 1):
                notes_str = f" ({data['notes']})" if data.get('notes') else ""
                print(f"  {i}. {data['name']} -> {ip}{notes_str}")
        print("-" * 55)
        print("  1. Add or Update Peer Name for an IP")
        print("  2. Delete a Peer Alias")
        print("  3. Back to Main Menu")
        print("-" * 55)

        opt = input("Select action (1-3): ").strip()
        if opt == "1":
            target_ip = input("Enter peer IP address (LAN or Tailscale 100.x.x.x): ").strip()
            if target_ip:
                custom_name = input(f"Enter friendly name for {target_ip}: ").strip()
                notes = input("Enter optional notes (e.g. Living room Mac): ").strip()
                if custom_name:
                    set_peer_alias(target_ip, custom_name, notes)
                    print(f"✅ Saved alias: '{custom_name}' for IP {target_ip}")
        elif opt == "2":
            target_ip = input("Enter IP to remove alias for: ").strip()
            if target_ip:
                if delete_peer_alias(target_ip):
                    print(f"✅ Removed alias for {target_ip}")
                else:
                    print(f"⚠️ No alias found for {target_ip}")
        elif opt in ("3", "b", "q"):
            break

def interactive_send_flow(udp_server: UDPDiscoveryServer):
    """Interactive multi-folder & file batch transmission flow."""
    peers = udp_server.get_active_peers()
    if not peers:
        discovered = discover_peers(timeout=1.0)
        for p in discovered:
            with udp_server.lock:
                udp_server.peers[p["ip"]] = p
        peers = udp_server.get_active_peers()

    print("\nSelect target peer:")
    if not peers:
        print("   No active peers discovered via beacon.")
        target_ip = input("   Enter target IP manually: ").strip()
    else:
        for i, p in enumerate(peers, 1):
            ptype = f"[{p.get('type', 'lan').upper()}]"
            print(f"   {i}. {p['name']} ({p['ip']}) {ptype} - {p.get('latency', 0)}ms")
        choice = input(f"Select peer (1-{len(peers)}) or type IP: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(peers):
            target_ip = peers[int(choice) - 1]["ip"]
        else:
            target_ip = choice.strip()

    if not target_ip:
        print("❌ Target IP is required.")
        return

    print("\nEnter paths to send. You can specify MULTIPLE folders and files.")
    print("Example: /path/to/folder1, /path/to/folder2, /path/to/file.pdf")
    raw_paths = input("Path(s): ").strip()
    if not raw_paths:
        return

    # Parse comma-separated or single paths
    path_list = [p.strip().strip('"').strip("'") for p in raw_paths.split(",") if p.strip()]
    valid_paths = [p for p in path_list if os.path.exists(p)]
    if not valid_paths:
        print("❌ None of the specified paths exist.")
        return

    print(f"\n📦 Enqueuing {len(valid_paths)} path(s) to {target_ip}...")
    batch = queue_manager.enqueue_paths(target_ip=target_ip, paths=valid_paths)
    print(f"   Batch ID: {batch.id}")
    print(f"   Total Files: {len(batch.tasks)} | Total Size: {format_bytes(batch.total_bytes)}")
    print(f"   Encryption : {'AES-256-GCM' if state.encryption_enabled else 'Plaintext'}")
    print(f"   Compression: {'Gzip Active' if state.compression_enabled else 'None'}\n")

    # Interactive progress monitor
    print("🚀 Transmitting batch...")
    last_file = ""
    while batch.status in (TransferStatus.QUEUED, TransferStatus.IN_PROGRESS):
        batch.update_aggregate_metrics()
        active_task = next((t for t in batch.tasks if t.status == TransferStatus.IN_PROGRESS), None)
        if active_task and active_task.filename != last_file:
            last_file = active_task.filename
        
        pct = batch.progress_percent
        speed_mb = batch.speed / (1024 * 1024)
        speed_mbps = (batch.speed * 8) / (1024 * 1024)
        eta_str = f"{batch.eta:.1f}s" if batch.eta > 0 else "calculating"
        cur_file_str = f"[{active_task.filename[:14]} {active_task.progress_percent:.0f}%]" if active_task else "[Preparing]"

        sys.stdout.write(f"\r   Progress: {pct:5.1f}% | {cur_file_str:<22} | Speed: {speed_mb:6.2f} MB/s ({speed_mbps:5.1f} Mbps) | ETA: {eta_str:<10}")
        sys.stdout.flush()
        time.sleep(0.15)

    sys.stdout.write("\n")
    if batch.status == TransferStatus.COMPLETED:
        print(f"✅ Batch completed successfully! Transferred {len(batch.tasks)} file(s) ({format_bytes(batch.total_bytes)}).")
    elif batch.status == TransferStatus.FAILED:
        print("❌ Batch transfer encountered errors:")
        for t in batch.tasks:
            if t.status == TransferStatus.FAILED:
                print(f"   - {t.relative_path}: {t.error_message}")

def run_interactive_cli():
    """Main interactive terminal dashboard."""
    # 1. Load MongoDB settings
    load_settings()

    # 2. Start TCP Server Engine
    tcp_server = start_tcp_server()

    # 3. Start UDP Discovery Beacon
    udp_server = UDPDiscoveryServer()
    udp_server.start()

    # 4. Start Web REST API in background
    web_server, web_port = start_web_server(open_browser=False)

    print_banner()
    print("\n🟢 LocalShare Node active. Type 'help' or select an option below:")

    while True:
        try:
            print("\n" + "=" * 48)
            print("                MAIN MENU")
            print("=" * 48)
            print("  1. 📡 Scan & List Active Peers")
            print("  2. 📁 Send Files / Multiple Folders (Batch)")
            print("  3. 📋 Sync Clipboard / Send Text Snippet")
            print("  4. 📊 View Transfer Queue Status")
            print("  5. 🏷️  Manage Peer Names & Aliases (MongoDB)")
            print("  6. ⚙️  Settings & Preferences Panel")
            print("  7. 🌐 Tailscale Network Explorer")
            print("  8. 📱 Show Mobile QR Code")
            print("  9. 🧹 Purge Memory / Clear History")
            print("  0. 🚪 Exit / Shutdown")
            print("=" * 48)

            cmd = input("Select an option (0-9) or enter command: ").strip()
            if not cmd:
                continue

            if cmd in ("1", "scan", "ls", "peers"):
                print("\n📡 Discovering mesh peers across LAN & Tailscale...")
                discovered = discover_peers(timeout=1.5)
                for p in discovered:
                    with udp_server.lock:
                        udp_server.peers[p["ip"]] = p
                peers = udp_server.get_active_peers()
                if not peers:
                    print("   No active peers found. Make sure other LocalShare devices are online.")
                else:
                    print(f"   Found {len(peers)} active peer(s):")
                    for i, p in enumerate(peers, 1):
                        ptype = f"[{p.get('type', 'lan').upper()}]"
                        print(f"   {i}. {p['name']} ({p['ip']}:{p.get('port', TCP_PORT)}) {ptype} - {p.get('latency', 0)}ms")

            elif cmd in ("2", "send", "batch"):
                interactive_send_flow(udp_server)

            elif cmd in ("3", "text", "clip", "clipboard"):
                text = input("Enter text or snippet to send (leave empty to send system clipboard): ").strip()
                if not text:
                    text = get_system_clipboard()
                    if not text:
                        print("⚠️ System clipboard is empty.")
                        continue
                    print(f"Using clipboard: \"{text[:50]}...\"")

                peers = udp_server.get_active_peers()
                print("\nSend destination:")
                print("  0. Broadcast to ALL discovered peers")
                for i, p in enumerate(peers, 1):
                    print(f"  {i}. {p['name']} ({p['ip']})")
                
                dest = input(f"Choose (0-{len(peers)}) or type IP: ").strip()
                if dest == "0":
                    count = broadcast_text(text, peers, encrypt=state.encryption_enabled)
                    print(f"✅ Broadcasted text snippet to {count} peer(s).")
                elif dest.isdigit() and 1 <= int(dest) <= len(peers):
                    tip = peers[int(dest) - 1]["ip"]
                    ok, msg = send_text_snippet(tip, text, encrypt=state.encryption_enabled)
                    print(f"{'✅' if ok else '❌'} {msg}")
                elif dest:
                    ok, msg = send_text_snippet(dest, text, encrypt=state.encryption_enabled)
                    print(f"{'✅' if ok else '❌'} {msg}")

            elif cmd in ("4", "queue", "status"):
                batches = queue_manager.get_all_batches()
                print(f"\n📊 Transfer Batches ({len(batches)}):")
                if not batches:
                    print("   Queue is currently empty.")
                for b in batches:
                    print(f"\n   📦 Batch: {b['id'][:8]}... -> {b['target_name']} ({b['target_ip']})")
                    print(f"      Status: {b['status']} | Files: {b['completed_files']}/{b['total_files']} | Progress: {b['progress_percent']}%")
                    print(f"      Size  : {format_bytes(b['transferred_bytes'])} / {format_bytes(b['total_bytes'])}")
                    for t in b["tasks"]:
                        print(f"      - {t['relative_path']} [{t['status']}] {t['progress_percent']}%")

            elif cmd in ("5", "alias", "names"):
                manage_peer_aliases()

            elif cmd in ("6", "settings", "config"):
                show_settings_panel()

            elif cmd in ("7", "tailscale", "ts"):
                print("\n🌐 Querying Tailscale daemon...")
                ts_status = get_tailscale_status()
                if not ts_status.get("active"):
                    print(f"⚠️ Tailscale inactive or not installed: {ts_status.get('reason')}")
                else:
                    self_info = ts_status.get("Self", {})
                    print(f"   Node Name   : {self_info.get('HostName')}")
                    print(f"   Tailscale IP: {self_info.get('TailscaleIPs', ['None'])[0]}")
                    print(f"   OS          : {self_info.get('OS')}")
                    
                    ts_peers = get_tailscale_peers()
                    print(f"\n   Online Tailscale Peers ({len(ts_peers)}):")
                    for p in ts_peers:
                        alias_tag = f" (Alias: {p['custom_alias']})" if p.get("custom_alias") else ""
                        print(f"   - {p['name']} [{p['ip']}] (OS: {p['os']}){alias_tag}")

            elif cmd in ("8", "qr"):
                net_info = get_network_interfaces()
                url = f"http://{net_info['primary']}:{web_port}"
                print(f"\n📱 Connect Mobile / Browser to: {url}")
                print(generate_qr_code_ascii(url))

            elif cmd in ("9", "clear", "purge"):
                state.clear_memory()
                queue_manager.clear_completed()
                print("🧹 Memory logs purged and garbage collector executed.")

            elif cmd in ("0", "exit", "quit", "q"):
                print("\nShutting down LocalShare...")
                udp_server.stop()
                stop_tcp_server()
                os._exit(0)

            elif cmd in ("h", "help"):
                print_banner()

            else:
                print(f"Unknown command '{cmd}'. Type 'help' for options.")

        except (KeyboardInterrupt, EOFError):
            print("\nShutting down LocalShare...")
            udp_server.stop()
            stop_tcp_server()
            os._exit(0)

def run_cli():
    """Main CLI argument parser entrypoint."""
    parser = argparse.ArgumentParser(description="LocalShare 2.0 CLI Engine")
    subparsers = parser.add_subparsers(dest="subcommand")

    # server
    subparsers.add_parser("server", help="Run LocalShare headless server node")

    # scan
    subparsers.add_parser("scan", help="Scan LAN and Tailscale mesh for peers")

    # send
    send_p = subparsers.add_parser("send", help="Send files or multiple folders in batch")
    send_p.add_argument("paths", nargs="+", help="File and folder paths to send")
    send_p.add_argument("--target", required=True, help="Target peer IP address")

    # text
    text_p = subparsers.add_parser("text", help="Broadcast or send text snippet")
    text_p.add_argument("message", help="Message string")
    text_p.add_argument("--target", help="Target peer IP (optional)")

    # alias
    alias_p = subparsers.add_parser("alias", help="Assign friendly name to IP in MongoDB")
    alias_p.add_argument("ip", help="Target IP address")
    alias_p.add_argument("name", help="Friendly name alias")
    alias_p.add_argument("--notes", default="", help="Optional notes")

    # tailscale
    subparsers.add_parser("tailscale", help="View Tailscale mesh status and online nodes")

    # mcp
    subparsers.add_parser("mcp", help="Run LocalShare FastMCP service")

    args = parser.parse_args()

    if args.subcommand == "scan":
        print("🔍 Scanning for LocalShare peers...")
        peers = discover_peers(timeout=2.0)
        print(f"Discovered {len(peers)} device(s):")
        for p in peers:
            print(f" - {p['name']} ({p['ip']}:{p.get('port', TCP_PORT)}) [{p.get('type', 'lan').upper()}]")

    elif args.subcommand == "send":
        load_settings()
        print(f"📦 Enqueuing {len(args.paths)} path(s) to {args.target}...")
        batch = queue_manager.enqueue_paths(target_ip=args.target, paths=args.paths)
        print(f"Batch {batch.id} started with {len(batch.tasks)} files ({format_bytes(batch.total_bytes)}).")
        while batch.status in (TransferStatus.QUEUED, TransferStatus.IN_PROGRESS):
            batch.update_aggregate_metrics()
            active_task = next((t for t in batch.tasks if t.status == TransferStatus.IN_PROGRESS), None)
            pct = batch.progress_percent
            speed_mb = batch.speed / (1024 * 1024)
            speed_mbps = (batch.speed * 8) / (1024 * 1024)
            eta_str = f"{batch.eta:.1f}s" if batch.eta > 0 else "calculating"
            cur_file_str = f"[{active_task.filename[:14]} {active_task.progress_percent:.0f}%]" if active_task else "[Preparing]"
            sys.stdout.write(f"\r   Progress: {pct:5.1f}% | {cur_file_str:<22} | Speed: {speed_mb:6.2f} MB/s ({speed_mbps:5.1f} Mbps) | ETA: {eta_str:<10}")
            sys.stdout.flush()
            time.sleep(0.15)
        sys.stdout.write("\n")
        print(f"Status: {batch.status.value}")

    elif args.subcommand == "text":
        load_settings()
        if args.target:
            ok, msg = send_text_snippet(args.target, args.message)
            print(f"{'✅' if ok else '❌'} {msg}")
        else:
            peers = discover_peers(timeout=1.5)
            count = broadcast_text(args.message, peers)
            print(f"Broadcasted to {count} peer(s).")

    elif args.subcommand == "alias":
        set_peer_alias(args.ip, args.name, args.notes)
        print(f"✅ Alias saved in MongoDB: '{args.name}' for {args.ip}")

    elif args.subcommand == "tailscale":
        ts_peers = get_tailscale_peers()
        print(f"Online Tailscale Peers ({len(ts_peers)}):")
        for p in ts_peers:
            print(f" - {p['name']} ({p['ip']}) [OS: {p['os']}]")

    elif args.subcommand == "mcp":
        from app.mcp.server import run_mcp_service
        run_mcp_service()

    elif args.subcommand == "server":
        load_settings()
        start_tcp_server()
        udp_server = UDPDiscoveryServer()
        udp_server.start()
        start_web_server(open_browser=False)
        print("🟢 Headless LocalShare server running. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            udp_server.stop()
            stop_tcp_server()

    else:
        # Default: launch full interactive terminal dashboard
        run_interactive_cli()
