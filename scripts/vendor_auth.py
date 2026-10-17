"""Copy af-auth into a product that ships without third-party packages.

    python scripts/vendor_auth.py ../MyProduct   # server/afauth.py and js/vendor/af-auth.js

Every copy carries a two-line header and is otherwise byte-identical; packages/af-auth/tests fail on a stale copy.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / 'packages' / 'af-auth'
SRC = PKG / 'af_auth.py'
VERSION = next(line.split("'")[1] for line in SRC.read_text().splitlines() if line.startswith('__version__'))


def _first(repo, *options):
    return next((repo / o for o in options if (repo / o).is_dir()), repo / options[-1])


def destinations(repo):
    repo = Path(repo)
    return [
        (SRC, repo / 'server' / 'afauth.py'),
        (PKG / 'af-auth.js', _first(repo, 'web/js', 'js') / 'vendor' / 'af-auth.js'),
    ]


def header(dest):
    a = f'Vendored from Apps-Factory packages/af-auth {VERSION} - do not edit here.'
    b = 'Update with: python scripts/vendor_auth.py <product repo> (from the Apps-Factory checkout)'
    return f'# {a}\n# {b}\n' if dest.suffix == '.py' else f'/* {a} */\n/* {b} */\n'


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    repo = Path(argv[1]).resolve()
    if not (repo / 'server').is_dir():
        print('No server/ folder in', repo)
        return 2
    for src, dest in destinations(repo):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(header(dest).encode() + src.read_bytes())
        print('wrote', dest)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
