"""Copy the telemetry outbox into a product that ships without third-party packages.

    python scripts/vendor_telemetry.py ../Store
    # writes server/aftelemetry.py, server/aftelemetry_events.json (verbatim), <js>/vendor/af-telemetry.js, <css>/af-telemetry.css

Code copies carry a two-line header; the taxonomy JSON is copied byte-for-byte. packages/af-telemetry/tests fail on a
stale copy. A product that needs more event types adds them to the factory taxonomy (reviewed), never to its copy.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / 'packages' / 'af-telemetry'
VERSION = next(line.split("'")[1] for line in (PKG / 'af_telemetry.py').read_text().splitlines() if line.startswith('__version__'))


def _first(repo, *options):
    return next((repo / o for o in options if (repo / o).is_dir()), repo / options[-1])


def destinations(repo):
    """(source, destination, has_header)."""
    repo = Path(repo)
    return [(PKG / 'af_telemetry.py', repo / 'server' / 'aftelemetry.py', True),
            (PKG / 'events.json', repo / 'server' / 'aftelemetry_events.json', False),
            (PKG / 'af-telemetry.js', _first(repo, 'web/js', 'js') / 'vendor' / 'af-telemetry.js', True),
            (PKG / 'af-telemetry.css', _first(repo, 'web/css', 'css') / 'af-telemetry.css', True)]


def header(dest):
    a = f'Vendored from Apps-Factory packages/af-telemetry {VERSION} - do not edit here.'
    b = 'Update with: python scripts/vendor_telemetry.py <product repo> (from the Apps-Factory checkout)'
    return f'# {a}\n# {b}\n' if dest.suffix == '.py' else f'/* {a} */\n/* {b} */\n'


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    repo = Path(argv[1]).resolve()
    if not (repo / 'server').is_dir():
        print('No server/ folder in', repo)
        return 2
    for src, dest, headed in destinations(repo):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes((header(dest).encode() if headed else b'') + src.read_bytes())
        print('wrote', dest)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
