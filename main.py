"""
LocalShare Master Entrypoint (main.py)
"""

import sys
import os

def main():
    try:
        first_arg = sys.argv[1].lower() if len(sys.argv) > 1 else ""

        if first_arg == "mcp":
            from app.mcp.server import run_mcp_service
            run_mcp_service()
        elif first_arg == "cli":
            sys.argv.pop(1)
            from app.cli.main import run_cli
            run_cli()
        elif first_arg in ("server", "scan", "send", "text", "alias", "logs", "tailscale", "mouse"):
            from app.cli.main import run_cli
            run_cli()
        elif first_arg in ("host", "client"):
            sys.argv.insert(1, "mouse")
            from app.cli.main import run_cli
            run_cli()
        elif first_arg == "ui":
            try:
                from app.ui.app import launch_ui
                launch_ui()
            except Exception as e:
                print(f"⚠️ UI dependencies unavailable ({e}). Install with: pip install customtkinter pillow darkdetect")
                print("Launching interactive CLI dashboard instead...")
                from app.cli.main import run_cli
                run_cli()
        else:
            # Default launcher: Launch CLI dashboard directly
            from app.cli.main import run_cli
            run_cli()
    except (KeyboardInterrupt, EOFError):
        print("\n👋 LocalShare stopped.")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)

if __name__ == "__main__":
    main()
