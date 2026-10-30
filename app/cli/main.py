"""
Interactive Command Line Interface (CLI Engine) for LocalShare
Rich terminal dashboard, multi-folder batch queuing, local JSON settings manager, single log file, and Tailscale peer resolver.
"""

import sys
import os
import time
import argparse
from app.config import state, TCP_PORT, INPUT_PORT, LOG_FILE, CONFIG_FILE, DEFAULT_UPLOAD_DIR
from app.utils import get_network_interfaces
from app.storage import (
    load_settings, save_settings, get_settings_dict,
    get_peer_alias, set_peer_alias, delete_peer_alias, get_all_peer_aliases,
    get_transfer_history, get_recent_log_lines, log_info
)
from app.security.encryption import generate_key, encrypt_text, decrypt_text
from app.discovery.udp_beacon import UDPDiscoveryServer, discover_peers
from app.discovery.tailscale import get_tailscale_peers, get_tailscale_status
from app.queue.manager import queue_manager
from app.queue.models import TransferStatus
from app.transfer.server import start_tcp_server, stop_tcp_server
from app.transfer.client import send_single_file, send_batch, send_text_snippet
from app.sync.clipboard import get_system_clipboard, set_system_clipboard, broadcast_text

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

    print("\n" + "=" * 68)
    print("  🚀 LOCALSHARE 2.0 - High-Speed Encrypted Mesh File Transfer")
    print("=" * 68)
    print(f" 💻 Device Name   : {state.device_name}")
    print(f" 🌐 Primary LAN IP : {net_info['primary']} (Port: {TCP_PORT})")
    if net_info.get("tailscale"):
        print(f" 🔒 Tailscale IP   : {net_info['tailscale']} [Active]")
    print(f" 🔐 Encryption     : {'🟢 AES-256-GCM Active' if state.encryption_enabled and state.encryption_key else '⚪ Disabled'}")
    print(f" ⚡ Compression    : {'🟢 Gzip (Level ' + str(state.compression_level) + ')' if state.compression_enabled else '⚪ Disabled'}")
    print(f" 📁 Upload Folder  : {os.path.abspath(state.upload_dir)}")
    print(f" 📝 Log File       : {LOG_FILE}")
    print("=" * 68)

def show_settings_panel():
    """Interactive Settings & Preferences Manager."""
    while True:
        print("\n" + "-" * 50)
        print("         ⚙️  SETTINGS & PREFERENCES PANEL")
        print("-" * 50)
        print(f" 1. Device Name          : {state.device_name}")
        print(f" 2. Upload Directory     : {state.upload_dir}")
        print(f" 3. Auto-Approve Files   : {'✅ Enabled' if state.auto_approve else '❌ Prompt Required'}")
        print(f" 4. Gzip Compression    : {'✅ Enabled (Level ' + str(state.compression_level) + ')' if state.compression_enabled else '❌ Disabled'}")
        print(f" 5. AES-256 Encryption   : {'✅ Enabled' if state.encryption_enabled else '❌ Disabled'}")
        print(f" 6. Encryption Key       : {state.encryption_key[:12] + '...' if state.encryption_key else '<Not Set>'}")
        print(f" 7. Config & Log Paths   : {CONFIG_FILE}")
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
            print(f"\n📂 Local Storage Details:")
            print(f"   Config File : {CONFIG_FILE}")
            print(f"   Log File    : {LOG_FILE}")
            input("\nPress Enter to continue...")

        elif choice == "8" or choice.lower() in ("b", "q", "exit"):
            break

def manage_peer_aliases():
    """Interactive Peer Name & Alias Manager."""
    while True:
        aliases = get_all_peer_aliases()
        print("\n" + "-" * 52)
        print("          🏷️  PEER NAME & ALIAS MANAGER")
        print("-" * 52)
        if not aliases:
            print("  (No custom peer aliases configured)")
        else:
            for ip, data in aliases.items():
                notes_str = f" - {data.get('notes')}" if data.get('notes') else ""
                print(f"  • {ip:<18} -> '{data['name']}'{notes_str}")
        print("-" * 52)
        print(" 1. Add / Update Peer Alias")
        print(" 2. Delete Peer Alias")
        print(" 3. Back to Main Menu")
        print("-" * 52)

        opt = input("Choose option (1-3): ").strip()
        if opt == "1":
            ip = input("Enter Peer IP (LAN or Tailscale): ").strip()
            if not ip:
                continue
            name = input(f"Enter custom friendly name for {ip}: ").strip()
            if not name:
                continue
            notes = input("Enter optional notes (e.g., 'Work Laptop'): ").strip()
            set_peer_alias(ip, name, notes)
            print(f"✅ Alias saved: '{name}' -> {ip}")

        elif opt == "2":
            ip = input("Enter IP of alias to delete: ").strip()
            if ip and delete_peer_alias(ip):
                print(f"✅ Deleted alias for {ip}")
            else:
                print("⚠️ Alias not found.")

        elif opt in ("3", "b", "q", "exit"):
            break

def interactive_send_flow(udp_server: UDPDiscoveryServer):
    """Guided flow for sending multiple files and folders in batch."""
    print("\n" + "=" * 50)
    print("       📁 MULTI-FOLDER BATCH SENDER")
    print("=" * 50)

    # 1. Collect target paths
    paths = []
    print("Enter file and directory paths (one per line).")
    print("Press Enter on an empty line when finished:")
    while True:
        p = input(f"Path #{len(paths) + 1} > ").strip().strip('"').strip("'")
        if not p:
            if paths:
                break
            else:
                print("⚠️ Please enter at least one file or folder path.")
                continue
        abs_p = os.path.abspath(os.path.expanduser(p))
        if not os.path.exists(abs_p):
            print(f"❌ Path does not exist: {abs_p}")
            continue
        paths.append(abs_p)
        print(f"   Added: {os.path.basename(abs_p)} ({'Folder' if os.path.isdir(abs_p) else 'File'})")

    # 2. Select Destination Peer
    peers = udp_server.get_active_peers()
    print("\nSelect Target Device:")
    if peers:
        for i, peer in enumerate(peers, 1):
            alias = get_peer_alias(peer['ip'])
            dname = f"{alias} ({peer['name']})" if alias else peer['name']
            ptype = peer.get('type', 'lan').upper()
            print(f"  {i}. {dname:<26} ({peer['ip']}) [{ptype}]")
    print(f"  {len(peers) + 1}. Enter IP address manually")

    choice = input(f"Choose target (1-{len(peers) + 1}): ").strip()
    target_ip = None
    target_name = None

    if choice.isdigit() and 1 <= int(choice) <= len(peers):
        selected = peers[int(choice) - 1]
        target_ip = selected["ip"]
        target_name = selected["name"]
    else:
        target_ip = input("Enter target IP address: ").strip()
        target_name = get_peer_alias(target_ip) or target_ip

    if not target_ip:
        print("❌ Invalid target IP. Aborted.")
        return

    # 3. Enqueue and initiate batch transfer
    print(f"\n📦 Enqueuing {len(paths)} path(s) to {target_name} ({target_ip})...")
    batch = queue_manager.enqueue_paths(target_ip=target_ip, paths=paths, target_name=target_name)
    print(f"🚀 Batch {batch.id[:8]} started: {len(batch.tasks)} files ({format_bytes(batch.total_bytes)} total)")

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
    if batch.status == TransferStatus.COMPLETED:
        print(f"✅ Batch completed successfully! Transferred {len(batch.tasks)} file(s) ({format_bytes(batch.total_bytes)}).")
    elif batch.status == TransferStatus.FAILED:
        print("❌ Batch transfer encountered errors:")
        for t in batch.tasks:
            if t.status == TransferStatus.FAILED:
                print(f"   - {t.relative_path}: {t.error_message}")

def show_recent_logs():
    """Display recent entries from ~/.localshare/localshare.log."""
    print("\n" + "=" * 68)
    print(f"       📝 UNIFIED LOG FILE: {LOG_FILE}")
    print("=" * 68)
    lines = get_recent_log_lines(limit=30)
    for line in lines:
        print(f"  {line}")
    print("=" * 68)
    input("\nPress Enter to return to main menu...")

def run_interactive_cli():
    """Main interactive terminal dashboard."""
    # 1. Load local JSON settings
    load_settings()

    # 2. Start TCP Server Engine
    tcp_server = start_tcp_server()

    # 3. Start UDP Discovery Beacon
    udp_server = UDPDiscoveryServer()
    udp_server.start()

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
            print("  5. 🏷️  Manage Peer Names & Aliases")
            print("  6. ⚙️  Settings & Preferences Panel")
            print("  7. 🌐 Tailscale Network Explorer")
            print("  8. 📝 View Unified Event & Transfer Logs")
            print("  9. 🧹 Purge Memory / Clear History")
            print("  m. 🖱️  Virtual KVM (Share Mouse Across Machines)")
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
                
                all_active = udp_server.get_active_peers()
                peer_map = {p["ip"]: p for p in all_active}
                for p in discovered:
                    peer_map[p["ip"]] = p
                peers = list(peer_map.values())

                if not peers:
                    print("   ⚠️  No active peers found.")
                    print("   💡 Make sure other LocalShare devices are online on LAN or Tailscale.\n")
                else:
                    print(f"   🟢 Found {len(peers)} active peer(s):\n")
                    print(f"   {'#':<3} {'Peer Name':<26} {'Address':<22} {'Network':<12} {'OS':<10} {'Latency'}")
                    print(f"   {'-'*3} {'-'*26} {'-'*22} {'-'*12} {'-'*10} {'-'*10}")
                    for i, p in enumerate(peers, 1):
                        ptype = p.get('type', 'lan').upper()
                        os_name = str(p.get('os', 'Unknown')).capitalize()
                        addr = f"{p['ip']}:{p.get('port', TCP_PORT)}"
                        lat = f"{p.get('latency', 0):.1f}ms"
                        print(f"   {i:<3} {p['name'][:26]:<26} {addr:<22} [{ptype:<9}] {os_name:<10} {lat}")
                    print()

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

            elif cmd in ("8", "logs", "log"):
                show_recent_logs()

            elif cmd in ("9", "clear", "purge"):
                state.clear_memory()
                queue_manager.clear_completed()
                print("🧹 Memory logs purged and garbage collector executed.")

            elif cmd.lower() in ("m", "mouse", "kvm"):
                print("\n🖱️  Virtual KVM Mode:")
                print("  1. Host (Share THIS computer's mouse with remote machine)")
                print("  2. Client (Control THIS computer with remote mouse)")
                kvm_choice = input("Select role (1-2) [1]: ").strip() or "1"
                if kvm_choice == "1":
                    from app.input.host import start_mouse_host
                    peers = udp_server.get_active_peers()
                    print("\nSelect Target Client Machine:")
                    if peers:
                        for i, peer in enumerate(peers, 1):
                            alias = get_peer_alias(peer['ip'])
                            dname = f"{alias} ({peer['name']})" if alias else peer['name']
                            print(f"  {i}. {dname:<26} ({peer['ip']})")
                    print(f"  {len(peers) + 1}. Enter IP address manually")
                    ch = input(f"Choose target (1-{len(peers) + 1}): ").strip()
                    tip = ""
                    if ch.isdigit() and 1 <= int(ch) <= len(peers):
                        tip = peers[int(ch) - 1]["ip"]
                    else:
                        tip = input("Enter target client IP: ").strip()
                    if tip:
                        start_mouse_host(target_ip=tip, edge="right")
                elif kvm_choice == "2":
                    from app.input.client import start_mouse_client
                    start_mouse_client(edge="left")

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
    subparsers.add_parser("server", help="Run LocalShare headless mesh node")

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
    alias_p = subparsers.add_parser("alias", help="Assign friendly name to IP")
    alias_p.add_argument("ip", help="Target IP address")
    alias_p.add_argument("name", help="Friendly name alias")
    alias_p.add_argument("--notes", default="", help="Optional notes")

    # logs
    subparsers.add_parser("logs", help="Display recent unified log entries")

    # tailscale
    subparsers.add_parser("tailscale", help="View Tailscale mesh status and online nodes")

    # mcp
    subparsers.add_parser("mcp", help="Run LocalShare FastMCP service")

    # mouse (Virtual KVM)
    mouse_p = subparsers.add_parser("mouse", help="Virtual KVM mouse sharing over LAN")
    mouse_sub = mouse_p.add_subparsers(dest="mouse_role", help="Host or Client")

    host_p = mouse_sub.add_parser("host", help="Run mouse host (shares this machine's mouse)")
    host_p.add_argument("target", nargs="?", default="", help="Target receiver IP (auto-discovers if omitted)")
    host_p.add_argument("--port", type=int, default=INPUT_PORT, help=f"UDP input port (default: {INPUT_PORT})")
    host_p.add_argument("--edge", choices=["right", "left"], default="right", help="Switching edge (default: right)")
    host_p.add_argument("--width", type=int, default=None, help="Display width override")
    host_p.add_argument("--height", type=int, default=None, help="Display height override")

    client_p = mouse_sub.add_parser("client", help="Run mouse receiver")
    client_p.add_argument("--port", type=int, default=INPUT_PORT, help=f"UDP bind port (default: {INPUT_PORT})")
    client_p.add_argument("--edge", choices=["left", "right"], default="left", help="Return edge (default: left)")
    client_p.add_argument("--width", type=int, default=None, help="Display width override")
    client_p.add_argument("--height", type=int, default=None, help="Display height override")

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
        print(f"✅ Alias saved: '{args.name}' for {args.ip}")

    elif args.subcommand == "logs":
        lines = get_recent_log_lines(limit=50)
        print(f"\n📝 Recent logs from {LOG_FILE}:")
        for line in lines:
            print(f"  {line}")

    elif args.subcommand == "tailscale":
        ts_peers = get_tailscale_peers()
        print(f"Online Tailscale Peers ({len(ts_peers)}):")
        for p in ts_peers:
            print(f" - {p['name']} ({p['ip']}) [OS: {p['os']}]")

    elif args.subcommand == "mcp":
        from app.mcp.server import run_mcp_service
        run_mcp_service()

    elif args.subcommand == "mouse":
        from app.input.host import start_mouse_host
        from app.input.client import start_mouse_client
        if args.mouse_role == "client":
            start_mouse_client(bind_port=args.port, edge=args.edge, width=args.width, height=args.height)
        elif args.mouse_role == "host":
            target_ip = args.target
            if not target_ip:
                print("🔍 Searching for LocalShare peers on LAN...")
                peers = discover_peers(timeout=1.5)
                if not peers:
                    print(f"❌ No peers found automatically. Usage: python3 main.py mouse host <IP>")
                    return
                print(f"Discovered {len(peers)} device(s):")
                for idx, p in enumerate(peers, 1):
                    alias = get_peer_alias(p['ip'])
                    dname = f"{alias} ({p['name']})" if alias else p['name']
                    print(f"  {idx}. {dname:<26} ({p['ip']})")
                sel = input(f"Select peer (1-{len(peers)}): ").strip()
                if sel.isdigit() and 1 <= int(sel) <= len(peers):
                    target_ip = peers[int(sel) - 1]['ip']
                else:
                    print("❌ Invalid selection.")
                    return
            start_mouse_host(target_ip=target_ip, target_port=args.port, edge=args.edge, width=args.width, height=args.height)
        else:
            mouse_p.print_help()

    elif args.subcommand == "server":
        load_settings()
        start_tcp_server()
        udp_server = UDPDiscoveryServer()
        udp_server.start()
        print("🟢 Headless LocalShare server running. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            udp_server.stop()
            stop_tcp_server()

    else:
        run_interactive_cli()
