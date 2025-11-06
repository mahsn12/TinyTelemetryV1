import socket as skt
from headers import Header
import threading, time
from globals import client_IP, client_port, server_IP, server_port

sequence_number = 1
device_id = 101

client_socket = skt.socket(family=skt.AF_INET, type=skt.SOCK_DGRAM)
client_socket.bind((client_IP, client_port))

init_header = Header(device_id=101, seq_num=0, msg_type=2)
init_packet = init_header.Pack_Init()


client_socket.sendto(init_packet, (server_IP, server_port))
print(f"[INFO] Running client (device {device_id})...")

def send_heartbeat():
    seq = 1
    while True:
        header = Header(device_id=device_id, seq_num=seq, msg_type=0)
        hb_packet = header.heartbeat()
        client_socket.sendto(hb_packet, (server_IP, server_port))
        print(f"[CLIENT] Sent HEARTBEAT seq={seq}")
        seq += 1
        time.sleep(30)

threading.Thread(target=send_heartbeat, daemon=True).start()

while True:
    header = Header(
        device_id=device_id,
        seq_num=sequence_number,
        flags=0
    )
    packet = header.Pack_Message()
    payload_value = 25.6 + sequence_number
    payload = str(round(payload_value, 2)).encode()
    packet += payload
    client_socket.sendto(packet, (server_IP, server_port))
    print(f"[CLIENT] Sent DATA seq={sequence_number}, value={payload_value:.2f}")
    sequence_number += 1
    time.sleep(6)
