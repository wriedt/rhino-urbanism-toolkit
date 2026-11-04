import json
import subprocess
import sys

router = r'C:\Users\rwr.ADEPT\AppData\Roaming\McNeel\Rhinoceros\ai\bin\rhino-mcp-router.exe'
proc = subprocess.Popen([router], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL, text=True, creationflags=0x08000000)

def send(payload):
    proc.stdin.write(json.dumps(payload) + '\n')
    proc.stdin.flush()

def request(i, method, params):
    send({'jsonrpc': '2.0', 'id': i, 'method': method, 'params': params})
    while True:
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError('Router closed the connection')
        response = json.loads(line)
        if response.get('id') == i:
            return response

try:
    request(1, 'initialize', {'protocolVersion': '2024-11-05', 'capabilities': {},
                            'clientInfo': {'name': 'urbanism-prototype-test', 'version': '1'}})
    send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
    if len(sys.argv) == 1:
        result = request(2, 'tools/list', {})
    else:
        args = json.loads(open(sys.argv[2], encoding='utf-8').read()) if len(sys.argv) > 2 else {}
        result = request(2, 'tools/call', {'name': sys.argv[1], 'arguments': args})
    print(json.dumps(result, indent=2))
finally:
    proc.terminate()
