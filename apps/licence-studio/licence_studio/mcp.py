"""MCP server (stdio, JSON-RPC 2.0) so an AI agent (Claude Code, Codex, …) can work with the Licence Studio.

The bridge holds no key and no passphrase. It calls the running studio's agent API with the token the owner created
(LS_AGENT_TOKEN) at LS_URL (default http://127.0.0.1:8770). What the agent may do is decided by the studio, not here:
read, check codes, request codes, and issue *trial* codes only if the owner allowed it.

Claude Code config (.mcp.json):
  {"mcpServers": {"licence-studio": {"command": "python", "args": ["-m", "licence_studio", "mcp"],
                   "cwd": "<Apps-Factory>/apps/licence-studio", "env": {"LS_AGENT_TOKEN": "lsa_…"}}}}
"""
from __future__ import annotations

import json
import os
import platform
import sys
import urllib.error
import urllib.parse
import urllib.request

PROTOCOL = '2025-06-18'
URL = os.environ.get('LS_URL', 'http://127.0.0.1:8770').rstrip('/')
TOKEN = os.environ.get('LS_AGENT_TOKEN', '')

S = lambda **p: {'type': 'object', 'properties': p, 'additionalProperties': False}  # noqa: E731
STR = {'type': 'string'}
INT = {'type': 'integer'}
TOOLS = [
    {'name': 'studio_doctor', 'description': 'Check this machine and the studio: Python, the cryptography library, the studio is '
     'running, the agent token works, a signing key exists and is unlocked. Returns the fix for anything missing.', 'inputSchema': S()},
    {'name': 'studio_status', 'description': 'Key present/unlocked, products, number of codes, pending requests, codes expiring in 3 days, '
     'and what the owner allows the agent to do.', 'inputSchema': S()},
    {'name': 'list_products', 'description': 'Products the studio can make codes for (id, name, trial days).', 'inputSchema': S()},
    {'name': 'list_codes', 'description': 'Issued codes, newest first. Filter by text (customer, phone, device, serial), product, and '
     'status: active | expiring | grace | expired | not_started.', 'inputSchema': S(query=STR, product=STR, status=STR)},
    {'name': 'get_code', 'description': 'One issued code by its serial (8 hex characters).', 'inputSchema': {**S(serial=STR), 'required': ['serial']}},
    {'name': 'verify_code', 'description': 'Check a code a customer pasted: valid?, state, terms, and whether this studio issued it. '
     'Give the device code for a full check.', 'inputSchema': {**S(code=STR, product=STR, device=STR), 'required': ['code', 'product']}},
    {'name': 'request_code', 'description': 'Ask the owner to approve a trial, monthly, lifetime or legacy code. Paid codes need owner approval.',
     'inputSchema': {**S(product=STR, device=STR, customer=STR, phone=STR, edition={'type': 'string', 'enum': ['trial', 'monthly', 'lifetime', 'standard', 'pro']},
                         days=INT, note=STR), 'required': ['product', 'customer']}},
    {'name': 'issue_trial_code', 'description': 'Issue a trial code tied to a device code (max 14 days). Works only if the owner '
     'allowed agents to issue trials and the studio is unlocked; otherwise it becomes a request for the owner.',
     'inputSchema': {**S(product=STR, device=STR, customer=STR, phone=STR, days=INT, note=STR), 'required': ['product', 'device', 'customer']}},
    {'name': 'list_requests', 'description': 'Code requests and their status (pending | approved | refused).', 'inputSchema': S(status=STR)},
]


def call_studio(method, path, body=None, query=None):
    url = URL + path
    if query:
        url += '?' + '&'.join(f'{k}={urllib.parse.quote(str(v))}' for k, v in query.items() if v)
    data = json.dumps(body or {}).encode() if method == 'POST' else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json',
                                          'Host': URL.split('//', 1)[1]})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read() or b'null')
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read())
        except ValueError:
            detail = {'error': str(e)}
        raise RuntimeError(f"{detail.get('error')} [{detail.get('key', e.code)}]")
    except urllib.error.URLError:
        raise RuntimeError(f'The Licence Studio is not running at {URL}. Start it: python -m licence_studio serve')


def doctor():
    checks = []
    ok = lambda name, good, fix='': checks.append({'check': name, 'ok': bool(good), **({'fix': fix} if not good else {})})  # noqa: E731
    ok('python >= 3.10', sys.version_info >= (3, 10), 'Install Python 3.12 from python.org')
    try:
        import cryptography  # noqa: F401
        ok('cryptography installed', True)
    except ImportError:
        ok('cryptography installed', False, 'pip install -r apps/licence-studio/requirements.txt')
    ok('agent token set', bool(TOKEN), 'Owner: open the studio → "AI agent" → create a token, put it in LS_AGENT_TOKEN')
    st = None
    try:
        st = call_studio('GET', '/agent/status')
        ok('studio reachable', True)
    except RuntimeError as e:
        ok('studio reachable', False, str(e))
    if st:
        ok('signing key exists', st['key'], 'Owner: open the studio → "Keys" → create the key (once) and back it up twice')
        ok('studio unlocked', st['unlocked'], 'Owner: unlock the studio with the passphrase (it locks itself after 30 idle minutes)')
    return {'machine': platform.platform(), 'studio_url': URL, 'checks': checks, 'all_ok': all(c['ok'] for c in checks)}


def run_tool(name, args):
    if name == 'studio_doctor':
        return doctor()
    if name == 'studio_status':
        return call_studio('GET', '/agent/status')
    if name == 'list_products':
        return call_studio('GET', '/agent/products')
    if name == 'list_codes':
        return call_studio('GET', '/agent/codes', query={'q': args.get('query'), 'product': args.get('product'), 'status': args.get('status')})
    if name == 'get_code':
        return call_studio('GET', '/agent/code', query={'serial': args['serial']})
    if name == 'verify_code':
        return call_studio('POST', '/agent/verify', args)
    if name == 'request_code':
        return call_studio('POST', '/agent/request', args)
    if name == 'issue_trial_code':
        return call_studio('POST', '/agent/issue_trial', args)
    if name == 'list_requests':
        return call_studio('GET', '/agent/requests', query={'status': args.get('status', 'pending')})
    raise KeyError(name)


def handle(msg):
    """One JSON-RPC message in, one response (or None for notifications) out."""
    mid, method, params = msg.get('id'), msg.get('method'), msg.get('params') or {}
    if mid is None:
        return None  # notifications (initialized, cancelled) need no answer
    if method == 'initialize':
        result = {'protocolVersion': PROTOCOL, 'capabilities': {'tools': {'listChanged': False}},
                  'serverInfo': {'name': 'licence-studio', 'title': 'Apps Factory Licence Studio', 'version': '1.0.0'},
                  'instructions': 'Codes are signed licences for the factory\'s products. Read and check freely; a code for a '
                                  'customer needs their device code (Settings → Licence in the product). Paid editions are only '
                                  'requested; the owner approves. Never ask for the passphrase or the private key.'}
    elif method == 'ping':
        result = {}
    elif method == 'tools/list':
        result = {'tools': TOOLS}
    elif method == 'tools/call':
        name = params.get('name')
        if name not in {t['name'] for t in TOOLS}:
            return {'jsonrpc': '2.0', 'id': mid, 'error': {'code': -32602, 'message': f'Unknown tool: {name}'}}
        try:
            out = run_tool(name, params.get('arguments') or {})
            result = {'content': [{'type': 'text', 'text': json.dumps(out, ensure_ascii=False, indent=1)}], 'structuredContent': {'result': out},
                      'isError': False}
        except (RuntimeError, KeyError) as e:
            result = {'content': [{'type': 'text', 'text': str(e)}], 'isError': True}
    else:
        return {'jsonrpc': '2.0', 'id': mid, 'error': {'code': -32601, 'message': f'Method not found: {method}'}}
    return {'jsonrpc': '2.0', 'id': mid, 'result': result}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            out = {'jsonrpc': '2.0', 'id': None, 'error': {'code': -32700, 'message': 'Parse error'}}
        else:
            out = handle(msg)
        if out is not None:
            sys.stdout.write(json.dumps(out, ensure_ascii=False) + '\n')
            sys.stdout.flush()

