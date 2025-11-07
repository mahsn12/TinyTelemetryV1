import socket as skt
from headers import Header
import csv , time
from globals import client_IP, client_port, server_IP, server_port

server_socket = skt.socket(family=skt.AF_INET, type=skt.SOCK_DGRAM)
server_socket.bind((server_IP, server_port))

print(f"[SERVER] Listening on UDP {server_IP}:{server_port}...\n")

temp_csv = open('temp.csv', 'w', newline='')
writer = csv.writer(temp_csv)

# ✅ Corrected header (added duplicate_flag + gap_flag)
writer.writerow(['device_id', 'seq_num', 'timestamp', 'msg_type', 'value', 'duplicate_flag', 'gap_flag','arival_time'])

packet_count = 0
bytes_total = 0
dup_count = 0
loss_count = 0

last_seq = {}

try:
    while True:
        packet, address = server_socket.recvfrom(1024)
        if len(packet) < Header.Size:
            print("[SERVER] Invalid packet size\n")
            continue

        header = Header()
        header.unPack(packet[:Header.Size])
        ts = time.time()
        if header.flags != 1 and header.msg_type == 1:
            continue

        dev = header.device_id
        seq = header.seq_num

        duplicate_flag = 0
        gap_flag = 0

        if dev in last_seq:
            if seq == last_seq[dev]:
                duplicate_flag = 1
                dup_count += 1
            elif seq > last_seq[dev] + 1:
                gap_flag = 1
                loss_count += 1

        last_seq[dev] = seq

        payload = packet[Header.Size:]
        value = payload.decode(errors='ignore')

        packet_count += 1
        bytes_total += len(packet)

        if header.msg_type == 0:
            print(f"[SERVER] HEARTBEAT from {dev}, time={header.timestamp}\n")
        elif header.msg_type == 2:
            print(f"[SERVER] INIT from {dev} , time={header.timestamp}\n")
        else:
            print(f"[SERVER] DATA from {dev} seq={seq}, value={value}, flags={header.flags}, time={header.timestamp}\n")

        writer.writerow([dev, seq, header.timestamp, header.msg_type, value, duplicate_flag, gap_flag,ts])
        temp_csv.flush()

except KeyboardInterrupt:
    print("\n\n[SERVER] Keyboard interrupt received. Shutting down...")

finally:
    if packet_count > 0:
        avg_bytes = bytes_total / packet_count
        print(f"[METRIC] bytes_per_report = {avg_bytes:.2f} bytes\n")
        print(f"[METRIC] packets_received = {packet_count}\n")
        print(f"[METRIC] Packets lost = {loss_count}\n")
        print(f"[METRIC] packets duplicated = {dup_count}\n")
    else:
        print("[METRIC] No packets received.\n")

    temp_csv.close()
    server_socket.close()
    print("[SERVER] Shutdown complete.\n")
