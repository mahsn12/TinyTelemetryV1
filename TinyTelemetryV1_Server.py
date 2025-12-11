import socket as skt
from headers import Header
import csv, time
from globals import client_IP, client_port, server_IP, server_port
import signal

running = True

def stop(sig, frame):
    global running
    running = False

signal.signal(signal.SIGINT, stop)

server_socket = skt.socket(family=skt.AF_INET, type=skt.SOCK_DGRAM)
server_socket.bind((server_IP, server_port))

print(f"[SERVER] Listening on UDP {server_IP}:{server_port}...\n")

temp_csv = open('temp.csv', 'w', newline='')
writer = csv.writer(temp_csv)

# CSV header (will only contain DATA packets)
writer.writerow(['device_id', 'seq_num', 'timestamp', 'value',
                 'duplicate_flag', 'gap_flag', 'arrival_time'])

# Metrics
packet_count = 0
bytes_total = 0
dup_count = 0
loss_count = 0

# Per-device last sequence for duplicate/loss detection
last_seq = {}

# Per-device reordering buffers
buffers = {}
BUFFER_THRESHOLD = 5   # only flush when buffer > 5
cpu_counts = 0
cpu_total_time = 0


try:
    while running:

        packet, address = server_socket.recvfrom(1024)

        if len(packet) < Header.Size:
            print("[SERVER] Invalid packet size\n")
            continue
        header = Header()
        header.unPack(packet[:Header.Size])
        arrival_time = time.time()

        dev = header.device_id
        seq = header.seq_num

        duplicate_flag = 0
        gap_flag = 0

        # ============= HANDLE HEARTBEAT & INIT =============
        if header.msg_type == 0:
            print(f"[SERVER] HEARTBEAT from {dev}, time={header.timestamp}\n")
            continue

        if header.msg_type == 2:
            print(f"[SERVER] INIT from {dev}, time={header.timestamp}\n")
            continue

        # ============= HANDLE DATA PACKET =============
        if header.msg_type == 1:
            cpu_start = time.process_time()

            # Sequence tracking
            if dev in last_seq:
                if seq == last_seq[dev]:
                    duplicate_flag = 1
                    dup_count += 1
                elif seq > last_seq[dev] + 1:
                    gap_flag = 1
                    loss_count += 1

            last_seq[dev] = seq

            # Decode payload
            payload = packet[Header.Size:]
            value = payload.decode(errors='ignore')

            # Update metrics
            packet_count += 1
            bytes_total += len(packet)

            print(f"[SERVER] DATA from {dev} seq={seq}, value={value}, "
                  f"time={header.timestamp}\n")

            # Create buffer for device if needed
            if dev not in buffers:
                buffers[dev] = []

            # Create packet entry
            packet_entry = (
                header.timestamp,   # 0 timestamp (sorting key)
                seq,                # 1 sequence number
                value,              # 2 value
                duplicate_flag,     # 3 duplicate flag
                gap_flag,           # 4 gap flag
                arrival_time,
            )

            # Add to buffer
            buffers[dev].append(packet_entry)

            # Sort by timestamp
            buffers[dev].sort(key=lambda x: x[0])
            cpu_end = time.process_time()
            cpu_counts+=1
            cpu_ms_per_packet = cpu_end - cpu_start

            cpu_total_time+=cpu_ms_per_packet
            # Flush oldest packet when buffer grows
            if len(buffers[dev]) > BUFFER_THRESHOLD:
                oldest = buffers[dev].pop(0)

                writer.writerow([
                    dev,
                    oldest[1],   # seq
                    oldest[0],   # timestamp
                    oldest[2],   # value
                    oldest[3],   # duplicate flag
                    oldest[4],   # gap flag
                    oldest[5],
                ])
                temp_csv.flush()


except KeyboardInterrupt:
    print("\n\n[SERVER] Keyboard interrupt received. Shutting down...")

finally:
    # Flush remaining packets from buffers
    for dev in buffers:
        buffers[dev].sort(key=lambda x: x[0])
        for pkt in buffers[dev]:
            writer.writerow([
                dev,
                pkt[1],  # seq
                pkt[0],  # timestamp
                pkt[2],  # value
                pkt[3],  # duplicate_flag
                pkt[4],  # gap_flag
                pkt[5]   # arrival_time
            ])

    # Print metrics
    if packet_count > 0:
        avg_bytes = bytes_total / packet_count
        print(f"[METRIC] bytes_per_report = {avg_bytes:.2f} bytes\n")
        print(f"[METRIC] packets_received = {packet_count}\n")
        print(f"[METRIC] Packets lost = {loss_count}\n")
        print(f"[METRIC] packets duplicated = {dup_count}\n")
        print(f"CPU_MS_PER_REPORT = {(cpu_total_time/cpu_counts) *1000}")
    else:
        print("[METRIC] No packets received.\n")

    temp_csv.close()
    server_socket.close()
    print("[SERVER] Shutdown complete.\n")
