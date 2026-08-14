"""
LocalShare Master Entrypoint (main.py)
"""

import sys
import os

def main():
    try:
        if len(sys.argv) > 1 and sys.argv[1].lower() == "mcp":
            from app.mcp.server import run_mcp_service
            run_mcp_service()
        else:
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
