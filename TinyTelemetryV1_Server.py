import socket as skt
from headers import Header
import time, csv
from globals import client_IP, client_port, server_IP, server_port

server_socket = skt.socket(family=skt.AF_INET, type=skt.SOCK_DGRAM)
server_socket.bind((server_IP, server_port))

print(f"[SERVER] Listening on UDP {server_IP}:{server_port}...\n")

temp_csv = open('temp.csv', 'w', newline='')
writer = csv.writer(temp_csv)
writer.writerow(['device_id', 'seq_num', 'timestamp', 'msg_type', 'value'])

packet_count = 0
bytes_total = 0

try:
    while True:
        packet, address = server_socket.recvfrom(1024)
        if len(packet) < Header.Size:
            print("[SERVER] Invalid packet size\n")
            continue

        header = Header()
        header.unPack(packet[:Header.Size])
        payload = packet[Header.Size:]
        value = payload.decode(errors='ignore')

        packet_count += 1
        bytes_total += len(packet)

        if header.msg_type == 0:
            print(f"[SERVER] HEARTBEAT from {header.device_id} seq={header.seq_num}, recv={header.timestamp}\n")
        elif header.msg_type == 2:
            print(f"[SERVER] INIT from {header.device_id} seq={header.seq_num}, value={value}, flags={header.flags}, recv={header.timestamp}\n")
        else:
            print(f"[SERVER] DATA from {header.device_id} seq={header.seq_num}, value={value}, flags={header.flags}, recv={header.timestamp}\n")

        writer.writerow([header.device_id, header.seq_num, header.timestamp, header.msg_type, value])
        temp_csv.flush()

except KeyboardInterrupt:
    print("\n\n[SERVER] Keyboard interrupt received. Shutting down...")

finally:
    if packet_count > 0:
        avg_bytes = bytes_total / packet_count
        print(f"[METRIC] bytes_per_report = {avg_bytes:.2f} bytes\n")
        print(f"[METRIC] packets_received = {packet_count}\n")
    else:
        print("[METRIC] No packets received.\n")
    temp_csv.close()
    server_socket.close()
    print("[SERVER] Shutdown complete.\n")