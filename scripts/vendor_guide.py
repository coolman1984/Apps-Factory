"""Copy the guide engine into a product that ships without third-party packages.

    python scripts/vendor_guide.py ../Store     # writes server/afguide.py, <js>/vendor/af-guide.js, <css>/af-guide.css

<js> is web/js or js, <css> is web/css or css (whichever the product has). Every copy carries a two-line header and
is otherwise byte-identical; packages/af-guide/tests/test_af_guide.py fails when a known product holds a stale copy.
Also check the product's guide in its own tests:  afguide.errors(catalogue, texts, ui=..., access=auth.catalogue())
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / 'packages' / 'af-guide'
VERSION = next(line.split("'")[1] for line in (PKG / 'af_guide.py').read_text().splitlines() if line.startswith('__version__'))


def _first(repo, *options):
    for o in options:
        if (repo / o).is_dir():
            return repo / o
    return repo / options[-1]


def destinations(repo):
    repo = Path(repo)
    js = _first(repo, 'web/js', 'js')
    css = _first(repo, 'web/css', 'css')
    return [(PKG / 'af_guide.py', repo / 'server' / 'afguide.py'),
            (PKG / 'af-guide.js', js / 'vendor' / 'af-guide.js'),
            (PKG / 'af-guide.css', css / 'af-guide.css')]


def header(dest):
    a = f'Vendored from Apps-Factory packages/af-guide {VERSION} - do not edit here.'
    b = 'Update with: python scripts/vendor_guide.py <product repo> (from the Apps-Factory checkout)'
    if dest.suffix == '.py':
        return f'# {a}\n# {b}\n'
    return f'/* {a} */\n/* {b} */\n'


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
