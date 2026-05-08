"""Entry point for clashctl when run as `python -m clashctl`."""

import sys

def main():
    args = sys.argv[1:]
    if args and args[0].lower() in ("web", "/web"):
        from .web import run_server
        host = "127.0.0.1"
        port = 9091
        secret = ""
        i = 1
        while i < len(args):
            arg = args[i]
            if arg == "--secret" and i + 1 < len(args):
                secret = args[i + 1]
                i += 2
            elif arg == "--no-auth":
                secret = ""
                i += 1
            elif not arg.startswith("-"):
                try:
                    port = int(arg)
                except ValueError:
                    host = arg
                i += 1
            else:
                i += 1
        run_server(host, port, secret)
    else:
        from .ui import main as ui_main
        ui_main()

main()
