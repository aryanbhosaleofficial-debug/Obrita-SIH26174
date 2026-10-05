"""Run the real offline Modules 01–05 pipeline; use --synthetic without assets."""
if __package__:
    from scripts._bootstrap import bootstrap
else:
    from _bootstrap import bootstrap
bootstrap()
from integration.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
