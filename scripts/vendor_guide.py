"""Copy the help gate (guides, learning paths, simple Arabic) into a product that ships without third-party packages.

    python scripts/vendor_guide.py ../Store            # writes server/afguide.py

The copy carries a two-line header and is otherwise byte-identical; packages/af-guide/tests/test_af_guide.py fails
when a known product holds a stale copy.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'packages' / 'af-guide' / 'af_guide.py'


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    target = Path(argv[1]).resolve() / 'server'
    if not target.is_dir():
        print('No server/ folder in', target.parent)
        return 2
    version = next(line.split("'")[1] for line in SRC.read_text().splitlines() if line.startswith('__version__'))
    header = (f'# Vendored from Apps-Factory packages/af-guide {version} af_guide.py - do not edit here.\n'
              '# Update with: python scripts/vendor_guide.py <product repo> (from the Apps-Factory checkout)\n')
    (target / 'afguide.py').write_bytes(header.encode() + SRC.read_bytes())
    print('wrote', target / 'afguide.py')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
