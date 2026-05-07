"""Entry point for clashctl when run as `python -m clashctl`."""

import sys

def main():
    args = sys.argv[1:]
    if args and args[0].lower() in ("web", "/web"):
        from .web import run_server
        host = "127.0.0.1"
        port = 9091
        if len(args) > 1:
            try:
                port = int(args[1])
            except ValueError:
                pass
        if len(args) > 2:
            host = args[2]
        run_server(host, port)
    else:
        from .ui import main as ui_main
        ui_main()

main()
