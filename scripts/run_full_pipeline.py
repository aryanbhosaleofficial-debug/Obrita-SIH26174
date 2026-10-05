"""Authoritative full-system launcher; legacy positional procedure demos retained."""
if __package__:
    from scripts._bootstrap import bootstrap
else:
    from _bootstrap import bootstrap
bootstrap()

import sys


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and not arguments[0].startswith("-"):
        # Historical positional command is a semantic-only compatibility demo.
        from procedure.demo import run_demo
        from procedure.procedure_loader import load_procedure
        from integration.full_cli import ROOT
        try:
            config = arguments[1] if len(arguments) > 1 else ROOT / "configs"
            return run_demo(load_procedure(arguments[0], config), legacy_output=True)
        except (OSError, ValueError) as exc:
            print(f"procedure configuration: {exc}", file=sys.stderr)
            return 1
    from integration.full_cli import main as full_main
    return full_main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
