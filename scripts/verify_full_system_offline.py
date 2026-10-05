"""Execute the full runner with outbound Python socket connections forbidden.

No interface/firewall configuration is changed. This verifies this execution,
not every possible native library path. Use installed local assets only.
"""
if __package__:
    from scripts._bootstrap import bootstrap
else:
    from _bootstrap import bootstrap
bootstrap()

import socket
import sys
from unittest.mock import patch
from integration.full_cli import main


def forbidden(*args, **kwargs):
    raise RuntimeError("offline verification: outbound network connection attempted")


if __name__ == "__main__":
    with patch.object(socket.socket, "connect", forbidden), patch.object(socket.socket, "connect_ex", forbidden), patch.object(socket, "create_connection", forbidden):
        raise SystemExit(main(sys.argv[1:]))
