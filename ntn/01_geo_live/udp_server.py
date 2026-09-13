import socket
import datetime

HOST = "0.0.0.0"
PORT = 5005

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((HOST, PORT))
print(f"Listening for UDP on {HOST}:{PORT} ...")

while True:
    data, addr = sock.recvfrom(4096)
    ts = datetime.datetime.now().isoformat(timespec="milliseconds")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.hex()
    print(f"[{ts}] {addr[0]}:{addr[1]} ({len(data)} bytes): {text}")
