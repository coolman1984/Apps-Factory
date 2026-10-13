"""Copy at-rest encryption helpers into a product (stdlib + optional sqlcipher3/cryptography).

    python scripts/vendor_atrest.py ../MyProduct   # writes server/afatrest.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / 'packages' / 'af-atrest'
VERSION = next(line.split("'")[1] for line in (PKG / 'af_atrest.py').read_text().splitlines() if line.startswith('__version__'))


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    repo = Path(argv[1]).resolve()
    if not (repo / 'server').is_dir():
        print('No server/ folder in', repo)
        return 2
    dest = repo / 'server' / 'afatrest.py'
    header = (
        f'# Vendored from Apps-Factory packages/af-atrest {VERSION} - do not edit here.\n'
        f'# Update with: python scripts/vendor_atrest.py <product repo> (from the Apps-Factory checkout)\n'
    )
    dest.write_bytes(header.encode() + (PKG / 'af_atrest.py').read_bytes())
    print('wrote', dest)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
