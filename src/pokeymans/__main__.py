"""Allow invoking pokeymans via `python -m pokeymans`."""

import sys

from pokeymans.cli.main import main

if __name__ == "__main__":
    sys.exit(main())
