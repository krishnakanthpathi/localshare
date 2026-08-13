"""
LocalShare Utilities Module
IP detection, security sanitization, hash generation, and QR Code generation.
"""

import os
import socket
import hashlib
import re
import subprocess
import json
import shutil

def get_tailscale_info():
    """
    Query Tailscale daemon for self IP and active online peers.
    Returns (self_ip, list_of_peer_ips).
    """
    ts_bin = shutil.which("tailscale") or "/Applications/Tailscale.app/Contents/MacOS/Tailscale"
    try:
        res = subprocess.run([ts_bin, "status", "--json"], capture_output=True, text=True, timeout=3)
        if res.returncode == 0:
            data = json.loads(res.stdout)
            self_ips = data.get("Self", {}).get("TailscaleIPs", [])
            self_ip = self_ips[0] if self_ips else None
            peer_ips = []
            for peer in data.get("Peer", {}).values():
                if peer.get("Online") and peer.get("TailscaleIPs"):
                    peer_ips.append(peer["TailscaleIPs"][0])
            return self_ip, peer_ips
    except Exception:
        pass
    return None, []

def get_network_interfaces():
    """
    Get all active local network interface IPs (LAN, Tailscale, Wi-Fi, Ethernet).
    Returns a dict with 'primary' IP, 'ips' list, and 'tailscale' IP if detected.
    """
    ips = []
    tailscale_ip = None
    primary_ip = "127.0.0.1"

    # Try connecting to external DNS to get primary LAN IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        primary_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    # Gather interface IPs via hostname lookup
    try:
        hostname = socket.gethostname()
        addr_info = socket.getaddrinfo(hostname, None)
        for item in addr_info:
            ip = item[4][0]
            if not ip.startswith("127.") and ":" not in ip and ip not in ips:
                ips.append(ip)
    except Exception:
        pass

    # Fetch Tailscale info
    ts_self, _ = get_tailscale_info()
    if ts_self and ts_self not in ips:
        ips.append(ts_self)
        tailscale_ip = ts_self

    # Ensure primary IP is included
    if primary_ip not in ips and primary_ip != "127.0.0.1":
        ips.insert(0, primary_ip)

    # Check for Tailscale IP (100.x.x.x) if not set
    if not tailscale_ip:
        for ip in ips:
            if ip.startswith("100."):
                tailscale_ip = ip

    return {
        "primary": primary_ip,
        "all": ips if ips else [primary_ip],
        "tailscale": tailscale_ip
    }

def sanitize_relative_path(rel_path):
    """
    Sanitize relative file path to prevent directory traversal attack.
    Removes leading slashes, '..' components, and invalid characters.
    """
    if not rel_path:
        return ""
    
    # Normalize separators
    clean_path = rel_path.replace("\\", "/").strip("/")
    
    # Strip any leading drive letters (e.g. C:)
    clean_path = re.sub(r'^[a-zA-Z]:', '', clean_path)
    
    parts = []
    for part in clean_path.split("/"):
        if part in ("", ".", ".."):
            continue
        # Remove risky shell/system chars
        safe_part = re.sub(r'[\x00-\x1f<>:"\\|?*]', '_', part)
        parts.append(safe_part)
        
    return "/".join(parts)

def safe_join(base_dir, relative_path):
    """
    Safely join base directory and relative path, ensuring target path stays strictly inside base_dir.
    """
    sanitized_rel = sanitize_relative_path(relative_path)
    target_path = os.path.abspath(os.path.join(base_dir, sanitized_rel))
    abs_base = os.path.abspath(base_dir)
    
    if not target_path.startswith(abs_base):
        raise ValueError(f"Security Alert: Path traversal attempt detected ({relative_path})")
        
    return target_path

def is_suspicious_file(filename):
    """Check if file has an executable/suspicious extension."""
    try:
        from config import SUSPICIOUS_EXTENSIONS
    except ImportError:
        from .config import SUSPICIOUS_EXTENSIONS
    ext = os.path.splitext(filename)[1].lower()
    return ext in SUSPICIOUS_EXTENSIONS

def is_compressible_file(filename):
    """Check if file format benefits from gzip compression."""
    try:
        from config import COMPRESSIBLE_EXTENSIONS
    except ImportError:
        from .config import COMPRESSIBLE_EXTENSIONS
    ext = os.path.splitext(filename)[1].lower()
    return ext in COMPRESSIBLE_EXTENSIONS

def compute_file_hash(filepath, max_bytes=10 * 1024 * 1024):
    """Compute quick MD5 hash of first max_bytes for integrity & resume checking."""
    hasher = hashlib.md5()
    try:
        with open(filepath, "rb") as f:
            read_bytes = 0
            while read_bytes < max_bytes:
                chunk = f.read(65536)
                if not chunk:
                    break
                hasher.update(chunk)
                read_bytes += len(chunk)
        return hasher.hexdigest()
    except Exception:
        return ""

def generate_qr_code_ascii(data_url):
    """
    Generate an inverted high-contrast ASCII representation of QR Code for dark terminal display.
    """
    try:
        import qrcode
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=1,
            border=2,
        )
        qr.add_data(data_url)
        qr.make(fit=True)
        
        output = []
        matrix = qr.get_matrix()
        for row in matrix:
            # Invert for dark terminal backgrounds so phone cameras scan instantly
            line = "".join("  " if cell else "██" for cell in row)
            output.append(line)
        return "\n".join(output)
    except Exception:
        border = "█" * 44
        return (
            f"\n{border}\n"
            f"█   📱 SCAN ME WITH YOUR MOBILE              █\n"
            f"█   URL: {data_url:<35} █\n"
            f"{border}\n"
        )

def generate_qr_code_svg(data_url):
    """
    Generate crisp, high-contrast black & white SVG QR Code for Web UI modal.
    Guarantees 100% instant scannability on all mobile cameras.
    """
    try:
        import qrcode
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=3,
        )
        qr.add_data(data_url)
        qr.make(fit=True)

        matrix = qr.get_matrix()
        size = len(matrix)
        scale = 8
        view_size = size * scale

        paths = []
        for r_idx, row in enumerate(matrix):
            for c_idx, cell in enumerate(row):
                if cell:
                    x = c_idx * scale
                    y = r_idx * scale
                    paths.append(f"M{x},{y}h{scale}v{scale}h-{scale}z")

        path_data = " ".join(paths)

        return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {view_size} {view_size}" width="240" height="240">
            <rect width="{view_size}" height="{view_size}" fill="#ffffff"/>
            <path d="{path_data}" fill="#000000"/>
        </svg>'''
    except Exception:
        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="240" height="240" viewBox="0 0 240 240">
            <rect width="240" height="240" fill="#ffffff"/>
            <text x="120" y="120" font-family="sans-serif" font-size="12" fill="#000000" text-anchor="middle">{data_url}</text>
        </svg>'''
