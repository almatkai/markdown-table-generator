#!/usr/bin/env python3
"""Real JSONL pipes; recording narrow host only, never the system clipboard."""
import json
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import uuid

COMMAND = 'generate-markdown-table'
VALIDATION = 'Please enter an integer value greater than zero for both rows and columns.'
SUCCESS = 'Markdown table copied to clipboard!'
TABLE = '| Column 1 | Column 2 |\n| --- | --- |\n| Cell 1-1 | Cell 1-2 |\n| Cell 2-1 | Cell 2-2 |\n'


class Peer:
    def __init__(self, binary, manifest, root, grants=None):
        self.temp = tempfile.TemporaryDirectory()
        self.calls = []
        self.messages = queue.Queue()
        env = {k: v for k, v in os.environ.items() if k in ('SystemRoot', 'WINDIR', 'TEMP', 'TMP')}
        env['PATH'] = os.path.join(env.get('SystemRoot', 'C:/Windows'), 'System32') if os.name == 'nt' else '/usr/bin:/bin'
        self.process = subprocess.Popen([str(binary.resolve())], cwd=root, env=env,
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        def reader():
            try:
                while True:
                    line = self.process.stdout.readline(16 * 1024 * 1024 + 1)
                    if not line:
                        self.messages.put(EOFError('Unexpected EOF'))
                        return
                    assert len(line) <= 16 * 1024 * 1024, 'Oversized frame'
                    self.messages.put(json.loads(line))
            except Exception as error:
                self.messages.put(error)
        threading.Thread(target=reader, daemon=True).start()
        hello = self.receive()
        assert hello['type'] == 'hello' and hello['protocol'] == 1, hello
        assert hello['id'] == manifest['id'] and hello['version'] == manifest['version'], hello
        assert hello['sdkVersion'] == '0.1.1', hello
        initialized = self.request('initialize', {
            'protocol': 1, 'extensionId': manifest['id'],
            'platform': 'Windows' if os.name == 'nt' else 'macOS',
            'packageDir': str(root.resolve()), 'dataDir': str(Path(self.temp.name) / 'data'),
            'tempDir': str(Path(self.temp.name) / 'temp'), 'reason': 'command',
            'grantedCapabilities': manifest['capabilities'] if grants is None else grants,
            'migrationPaths': {}})
        assert initialized['ready'] is True, initialized

    def send(self, frame):
        self.process.stdin.write((json.dumps(frame) + '\n').encode())
        self.process.stdin.flush()

    def start(self, method, params):
        ident = 'h:' + str(uuid.uuid4())
        self.send({'type': 'request', 'id': ident, 'method': method, 'params': params})
        return ident

    def receive(self):
        frame = self.messages.get(timeout=10)
        if isinstance(frame, Exception):
            raise frame
        return frame

    def response(self, ident, host=None, error=False):
        while True:
            frame = self.receive()
            if frame['type'] == 'request':
                assert frame['method'] == 'host.clipboard.write', frame
                assert set(frame['params']) == {'text'} and isinstance(frame['params']['text'], str), frame
                self.calls.append(frame)
                assert host is not None, 'Unexpected clipboard request'
                reply = host(frame)
                self.send(dict(type='response', id=frame['id'], **reply))
            else:
                assert frame['type'] == 'response' and frame['id'] == ident, frame
                assert ('error' in frame) == error, frame
                return frame['error'] if error else frame['result']

    def request(self, method, params, host=None, error=False):
        return self.response(self.start(method, params), host, error)

    def open(self, session, arguments, host=None):
        return self.request('session.open', {'sessionId': session, 'commandName': COMMAND,
                            'preferences': {}, 'argumentValues': arguments}, host)

    def dispose(self, session):
        self.request('session.dispose', {'sessionId': session})

    def close(self):
        try:
            if self.process.poll() is None:
                self.request('shutdown', {})
                assert self.process.wait(timeout=5) == 0
        finally:
            if self.process.poll() is None:
                self.process.kill()
                self.process.wait(timeout=5)
            self.process.stdin.close()
            self.process.stdout.close()
            stderr = self.process.stderr.read().decode()
            self.process.stderr.close()
            self.temp.cleanup()
            assert not stderr, stderr


def run_suite(binary, manifest, root):
    info = json.loads(subprocess.check_output([str(binary.resolve()), '--protocol-info'], timeout=10))
    assert info['id'] == manifest['id'] and info['version'] == manifest['version'] and info['protocol'] == 1
    assert info['commands'] == [COMMAND]
    peer = Peer(binary, manifest, root)
    try:
        # Real native acknowledgement shape. A successful open is immediately
        # disposed by the actual host, with stdin kept open throughout shutdown.
        def copy(frame):
            assert frame['params']['text'] == TABLE  # Includes actual multiline/trailing LF.
            return {'result': {'ok': True}}
        result = peer.open('success', {'rows': '2.9junk', 'columns': '\ufeff+02tail'}, copy)
        assert result == {'ok': True, 'mode': 'no-view', 'message': SUCCESS}, result
        assert len(peer.calls) == 1
        # This command has no bound actions: forged action/payload text must never copy.
        peer.request('session.call', {'sessionId': 'success', 'operation': 'extension:invoke-action',
                     'payload': {'actionId': 'copy', 'text': 'attacker text', 'argumentValues': {'rows': '9', 'columns': '9'}}}, error=True)
        peer.request('session.call', {'sessionId': 'success', 'operation': 'extension:refresh-session', 'payload': {}}, error=True)
        assert len(peer.calls) == 1
        peer.dispose('success')
        # Caller lifecycle for expected failures. >128 opens prove disposal is
        # accepted, SDK retains failed opens and there is no leaked session slot.
        for index in range(132):
            result = peer.open('invalid-' + str(index), {'rows': '0', 'columns': '2'})
            assert result == {'ok': False, 'mode': 'no-view', 'message': VALIDATION}, result
            peer.dispose('invalid-' + str(index))
        for index, args in enumerate(({}, {'rows': 1, 'columns': '2'}, {'rows': '1', 'columns': False},
                                    {'rows': '-3', 'columns': '2'}, {'rows': '1', 'columns': '0x10'})):
            sid = 'type-' + str(index)
            assert peer.open(sid, args) == {'ok': False, 'mode': 'no-view', 'message': VALIDATION}
            peer.dispose(sid)
        assert peer.open('limit', {'rows': '4125', 'columns': '136'}) == {
            'ok': False, 'mode': 'no-view', 'message': 'Markdown table exceeds the 8 MiB output limit.'}
        peer.dispose('limit')
        assert len(peer.calls) == 1
        # Exercise the engine's exact size boundary through the real JSONL frame,
        # including escaped newlines, not just a library-only allocation test.
        def copy_boundary(frame):
            text = frame['params']['text']
            assert len(text.encode()) == 8 * 1024 * 1024
            assert text.startswith('| Column 1 | Column 2 |')
            assert text.endswith(' Cell 4124-136 |\n')
            assert text.count('\n') == 4126
            return {'result': {'ok': True}}
        result = peer.open('boundary', {'rows': '4124', 'columns': '136'}, copy_boundary)
        assert result == {'ok': True, 'mode': 'no-view', 'message': SUCCESS}
        peer.dispose('boundary')
        # Real transport failure is not Copy success and still permits dispose.
        result = peer.open('denied', {'rows': '2', 'columns': '2'},
                           lambda frame: {'error': {'code': 'permission_denied', 'message': 'Clipboard permission denied'}})
        assert result == {'ok': False, 'mode': 'no-view', 'message': 'Clipboard permission denied'}
        peer.dispose('denied')
        # Malformed-envelope probes are separate from real native shapes.
        for index, ack in enumerate((None, 'copied', {}, {'ok': False, 'message': 'Write failed'},
                                    {'ok': True, 'success': False}, {'ok': True, 'error': 'Write failed'})):
            sid = 'malformed-' + str(index)
            result = peer.open(sid, {'rows': '2', 'columns': '2'}, lambda frame, ack=ack: {'result': ack})
            assert result['ok'] is False and result['mode'] == 'no-view' and result['message'] != SUCCESS
            peer.dispose(sid)
        # Hold the mandatory effect: success must not arrive before host ack.
        ident = peer.start('session.open', {'sessionId': 'waiting', 'commandName': COMMAND,
                           'preferences': {}, 'argumentValues': {'rows': '2', 'columns': '2'}})
        reverse = peer.receive()
        assert reverse['type'] == 'request' and reverse['method'] == 'host.clipboard.write', reverse
        assert reverse['params'] == {'text': TABLE}
        peer.send({'type': 'cancel', 'requestId': ident, 'reason': 'test cancellation'})
        seen = set()
        for _ in range(2):
            frame = peer.receive()
            if frame['type'] == 'cancel':
                assert frame['requestId'] == reverse['id'], frame
                seen.add('reverse cancelled')
            else:
                assert frame['type'] == 'response' and frame['id'] == ident and 'error' in frame, frame
                seen.add('operation cancelled')
        assert len(seen) == 2
        # Canceled open is removed by SDK, unlike handled domain failures. Late
        # host replies are ignored; no replay or synthetic success is allowed.
        peer.send({'type': 'response', 'id': reverse['id'], 'result': {'ok': True}})
        result = peer.open('after-cancel', {'rows': '2', 'columns': '2'}, copy)
        assert result['ok'] is True
        peer.dispose('after-cancel')
        peer.request('session.open', {'sessionId': 'unknown', 'commandName': 'missing', 'preferences': {}, 'argumentValues': {}}, error=True)
        peer.request('session.call', {'sessionId': 'missing', 'operation': 'made-up', 'payload': {}}, error=True)
    finally:
        peer.close()
    peer = Peer(binary, manifest, root, grants=[])
    try:
        result = peer.open('no-grant', {'rows': '2', 'columns': '2'})
        assert result['ok'] is False and result['mode'] == 'no-view', result
        assert not peer.calls
        peer.dispose('no-grant')
    finally:
        peer.close()
    print('Protocol lifecycle, exact copied text, domain failures/disposal, strict host acknowledgements, forged actions, cancellation and narrow grants passed.')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, default=Path(__file__).resolve().parents[1] / 'extension.json')
    args = parser.parse_args()
    run_suite(args.binary, json.loads(args.manifest.read_text()), args.manifest.parent)
