from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

def main() -> None:
    from mcp_entraid.server import mcp  # noqa: E402

    mcp.run(transport="http", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
