"""Copy the access-and-administration gate into a product that ships without third-party packages.

    python scripts/vendor_access.py ../Store            # writes server/afaccess.py

The copy carries a two-line header and is otherwise byte-identical; packages/af-access/tests/test_af_access.py fails
when a known product holds a stale copy.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'packages' / 'af-access' / 'af_access.py'


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    target = Path(argv[1]).resolve() / 'server'
    if not target.is_dir():
        print('No server/ folder in', target.parent)
        return 2
    version = next(line.split("'")[1] for line in SRC.read_text().splitlines() if line.startswith('__version__'))
    header = (f'# Vendored from Apps-Factory packages/af-access {version} af_access.py - do not edit here.\n'
              '# Update with: python scripts/vendor_access.py <product repo> (from the Apps-Factory checkout)\n')
    (target / 'afaccess.py').write_bytes(header.encode() + SRC.read_bytes())
    print('wrote', target / 'afaccess.py')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
