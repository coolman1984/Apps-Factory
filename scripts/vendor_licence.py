"""Copy the stdlib licence-code checker into a product that ships without third-party packages.

    python scripts/vendor_licence.py ../Store            # writes server/afcodes.py and server/ed25519.py

The copies carry a two-line header and are otherwise byte-identical; packages/af-license/tests/test_codes.py fails
when a known product holds a stale copy.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / 'packages' / 'af-license' / 'af_license'
FILES = {'codes.py': 'afcodes.py', 'ed25519_verify.py': 'ed25519.py'}


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    target = Path(argv[1]).resolve() / 'server'
    if not target.is_dir():
        print('No server/ folder in', target.parent)
        return 2
    version = next(line.split('"')[1] for line in (PKG / '__init__.py').read_text().splitlines() if line.startswith('__version__'))
    for src, dst in FILES.items():
        header = (f'# Vendored from Apps-Factory packages/af-license {version} af_license/{src} - do not edit here.\n'
                  '# Update with: python scripts/vendor_licence.py <product repo> (from the Apps-Factory checkout)\n')
        (target / dst).write_bytes(header.encode() + (PKG / src).read_bytes())
        print('wrote', target / dst)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
