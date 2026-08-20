"""
Transfer Benchmark & Variance Visualization Script for LocalShare
Streams the Lost episode video (380MB) from Mac to Linux Node over Tailscale,
captures real-time speed/throughput samples, and generates a detailed analytical plot.
"""

import os
import sys
import time
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from app.config import state, TCP_PORT
from app.transfer.client import send_single_file

TARGET_IP = "100.105.203.102"
SOURCE_FILE = "/Users/krishnakanth/Downloads/Lost.S02E08.1080p.BluRay.x265.@intermedia.mkv"
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_IMG = os.path.join(REPO_ROOT, "assets", "transfer_benchmark_analysis.png")

def run_benchmark():
    if not os.path.exists(SOURCE_FILE):
        print(f"❌ File not found: {SOURCE_FILE}")
        return

    filesize = os.path.getsize(SOURCE_FILE)
    filesize_mb = filesize / (1024 * 1024)
    print(f"🚀 Starting Benchmark Transmission of: {os.path.basename(SOURCE_FILE)}")
    print(f"📦 File Size : {filesize_mb:.2f} MB ({filesize:,} bytes)")
    print(f"🎯 Target    : {TARGET_IP}:{TCP_PORT} (Tailscale Mesh)")

    telemetry = []
    start_time = time.time()
    last_sample_t = [start_time]
    last_bytes = [0]

    def progress_callback(transferred, total, *args, **kwargs):
        now = time.time()
        elapsed = now - start_time
        transferred_mb = transferred / (1024 * 1024)
        pct = (transferred / total) * 100.0 if total > 0 else 0.0

        metrics = args[0] if args and isinstance(args[0], dict) else kwargs.get("metrics", {})
        speed_mb = metrics.get("speed_mb", 0.0) if metrics else (args[0] if args and isinstance(args[0], (int, float)) else 0.0)
        eta = metrics.get("eta", 0.0) if metrics else (args[1] if len(args) > 1 and isinstance(args[1], (int, float)) else 0.0)

        dt = now - last_sample_t[0]
        db = transferred - last_bytes[0]
        instant_speed = (db / (1024 * 1024)) / dt if dt > 0.05 else speed_mb

        if dt >= 0.15 or transferred >= total:
            last_sample_t[0] = now
            last_bytes[0] = transferred
            telemetry.append({
                "time": round(elapsed, 2),
                "transferred_mb": round(transferred_mb, 2),
                "percent": round(pct, 1),
                "instant_speed": max(0.0, instant_speed),
                "rolling_speed": speed_mb,
                "avg_speed": transferred_mb / elapsed if elapsed > 0 else 0.0
            })
            print(f"\r   ⏳ [{pct:5.1f}%] {transferred_mb:6.1f}/{filesize_mb:.1f} MB | Rolling: {speed_mb:6.2f} MB/s | Elapsed: {elapsed:4.1f}s | ETA: {eta:4.1f}s", end="", flush=True)

    print("\n📡 Initiating 4-worker parallel TCP transmission...")
    t0 = time.time()
    ok, msg = send_single_file(
        target_ip=TARGET_IP,
        file_path=SOURCE_FILE,
        progress_callback=progress_callback
    )
    total_time = time.time() - t0
    print("\n")

    if not ok:
        print(f"❌ Transfer failed: {msg}")
        return

    overall_avg_speed = filesize_mb / total_time
    print(f"✅ Transfer Completed in {total_time:.2f} seconds!")
    print(f"📊 Overall Average Throughput: {overall_avg_speed:.2f} MB/s ({overall_avg_speed * 8:.2f} Mbps)")
    print(f"📈 Total Telemetry Samples Captured: {len(telemetry)}")

    plot_benchmark(telemetry, filesize_mb, total_time, overall_avg_speed)

def plot_benchmark(telemetry, filesize_mb, total_time, overall_avg_speed):
    if not telemetry:
        print("⚠️ No telemetry samples to plot.")
        return

    times = [pt["time"] for pt in telemetry]
    trans_mb = [pt["transferred_mb"] for pt in telemetry]
    speeds = [pt["rolling_speed"] for pt in telemetry]
    inst_speeds = [pt["instant_speed"] for pt in telemetry]

    peak_speed = max(speeds) if speeds else 0.0
    min_speed = min([s for s in speeds if s > 0]) if any(s > 0 for s in speeds) else 0.0
    median_speed = float(np.median(speeds))
    std_dev = float(np.std(speeds))

    # Apply modern dark theme aesthetics
    plt.style.use("dark_background")
    fig = plt.figure(figsize=(14, 10), facecolor="#0e1117")
    gs = fig.add_gridspec(3, 2, height_ratios=[1.2, 1.0, 0.9], hspace=0.35, wspace=0.25)

    # -------------------------------------------------------------
    # Subplot 1: Throughput (MB/s) vs Time
    # -------------------------------------------------------------
    ax1 = fig.add_subplot(gs[0, :])
    ax1.set_facecolor("#161b22")
    
    ax1.fill_between(times, speeds, color="#38bdf8", alpha=0.25, label="Throughput Profile")
    ax1.plot(times, speeds, color="#38bdf8", lw=2.8, label=f"Rolling Window Speed (1.5s window)")
    if len(inst_speeds) > 1:
        ax1.plot(times, inst_speeds, color="#c084fc", lw=1.2, alpha=0.6, linestyle=":", label="Instantaneous Jitter")

    ax1.axhline(overall_avg_speed, color="#22c55e", linestyle="-.", lw=2.0, label=f"Average Speed: {overall_avg_speed:.2f} MB/s ({overall_avg_speed*8:.1f} Mbps)")
    ax1.axhline(peak_speed, color="#f59e0b", linestyle=":", lw=1.8, label=f"Peak Burst: {peak_speed:.2f} MB/s")

    ax1.set_title("🚀 Tailscale Mesh File Transfer Throughput Over Time (380 MB Video)", fontsize=14, fontweight="bold", color="#f8fafc", pad=12)
    ax1.set_xlabel("Elapsed Time (seconds)", fontsize=11, color="#94a3b8")
    ax1.set_ylabel("Transfer Speed (MB/s)", fontsize=11, color="#94a3b8")
    ax1.grid(True, linestyle="--", alpha=0.25, color="#475569")
    ax1.legend(loc="upper right", framealpha=0.85, facecolor="#1e293b", edgecolor="#334155")
    ax1.set_xlim(0, max(times) * 1.02 if times else 1)
    ax1.set_ylim(0, max(peak_speed * 1.25, 5))

    # -------------------------------------------------------------
    # Subplot 2: Cumulative Progress (MB) vs Time
    # -------------------------------------------------------------
    ax2 = fig.add_subplot(gs[1, 0])
    ax2.set_facecolor("#161b22")
    ax2.plot(times, trans_mb, color="#10b981", lw=2.5, label="Data Transferred (MB)")
    ax2.axhline(filesize_mb, color="#e2e8f0", linestyle=":", lw=1.5, label=f"Target: {filesize_mb:.1f} MB")
    ax2.set_title("📦 Cumulative Transfer Progression", fontsize=12, fontweight="bold", color="#f8fafc")
    ax2.set_xlabel("Elapsed Time (seconds)", fontsize=10, color="#94a3b8")
    ax2.set_ylabel("Data Transferred (MB)", fontsize=10, color="#94a3b8")
    ax2.grid(True, linestyle="--", alpha=0.25, color="#475569")
    ax2.legend(loc="lower right", framealpha=0.85, facecolor="#1e293b", edgecolor="#334155")

    # -------------------------------------------------------------
    # Subplot 3: Speed Distribution & Density (Histogram)
    # -------------------------------------------------------------
    ax3 = fig.add_subplot(gs[1, 1])
    ax3.set_facecolor("#161b22")
    ax3.hist(speeds, bins=12, color="#6366f1", alpha=0.75, edgecolor="#818cf8", rwidth=0.85)
    ax3.axvline(median_speed, color="#f43f5e", linestyle="--", lw=2, label=f"Median: {median_speed:.1f} MB/s")
    ax3.axvline(overall_avg_speed, color="#22c55e", linestyle="-.", lw=2, label=f"Mean: {overall_avg_speed:.1f} MB/s")
    ax3.set_title("📊 Throughput Distribution & Stability", fontsize=12, fontweight="bold", color="#f8fafc")
    ax3.set_xlabel("Throughput Bin (MB/s)", fontsize=10, color="#94a3b8")
    ax3.set_ylabel("Sample Count", fontsize=10, color="#94a3b8")
    ax3.grid(True, linestyle="--", alpha=0.25, color="#475569")
    ax3.legend(loc="upper right", framealpha=0.85, facecolor="#1e293b", edgecolor="#334155")

    # -------------------------------------------------------------
    # Subplot 4: Key Performance Indicators (KPI Cards)
    # -------------------------------------------------------------
    ax4 = fig.add_subplot(gs[2, :])
    ax4.set_facecolor("#161b22")
    ax4.axis("off")

    summary_text = (
        f"📊 TRANSFER TELEMETRY & NETWORK VARIANCE SUMMARY\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f" • Total Payload  : {filesize_mb:.2f} MB ({int(filesize_mb*1024*1024):,} bytes)            • Total Duration   : {total_time:.2f} seconds\n"
        f" • Average Speed  : {overall_avg_speed:.2f} MB/s ({overall_avg_speed*8:.2f} Mbps)            • Peak Throughput  : {peak_speed:.2f} MB/s ({peak_speed*8:.2f} Mbps)\n"
        f" • Minimum Speed  : {min_speed:.2f} MB/s ({min_speed*8:.2f} Mbps)            • Speed Variance σ : ±{std_dev:.2f} MB/s\n"
        f" • Parallel Streams: 4 Multi-Socket TCP Workers                  • Transport Route  : Tailscale WireGuard Mesh\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    ax4.text(0.5, 0.5, summary_text, color="#f1f5f9", fontsize=10.5, fontfamily="monospace",
             ha="center", va="center", bbox=dict(boxstyle="round,pad=0.8", facecolor="#1e293b", edgecolor="#3b82f6", lw=1.5))

    os.makedirs(os.path.dirname(OUTPUT_IMG), exist_ok=True)
    plt.savefig(OUTPUT_IMG, dpi=180, bbox_inches="tight")
    plt.close()
    print(f"🎉 Benchmark plot successfully generated and saved to:\n   {OUTPUT_IMG}")

if __name__ == "__main__":
    run_benchmark()
