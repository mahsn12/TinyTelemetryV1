import socket as skt
from headers import Header
import csv, time , struct
from globals import client_IP, client_port, server_IP, server_port
import signal

RUN_DURATION = 55


server_socket = skt.socket(family=skt.AF_INET, type=skt.SOCK_DGRAM)
server_socket.bind((server_IP, server_port))

# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
server_socket.settimeout(0.5)      # <── ONLY ADDITION #1
# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

print(f"[SERVER] Listening on UDP {server_IP}:{server_port}...\n")

temp_csv = open('temp.csv', 'w', newline='')
writer = csv.writer(temp_csv)

# CSV header
writer.writerow(['device_id', 'seq_num', 'timestamp', 'value',
                 'duplicate_flag', 'gap_flag', 'arrival_time'])

# Metrics
packet_count = 0
bytes_total = 0
dup_count = 0
loss_count = 0

# Per-device tracking
last_seq = {}
buffers = {}
BUFFER_THRESHOLD = 5

cpu_counts = 0
cpu_total_time = 0

start_time = time.time()

while (time.time() - start_time < RUN_DURATION):

        # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
        try:
            packet, address = server_socket.recvfrom(1024)
        except skt.timeout:
            continue                 # <── ONLY ADDITION #2
        # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

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


        # =====================================================
        # HEARTBEAT
        # =====================================================
        if header.msg_type == 0:
            print(f"[SERVER] HEARTBEAT from {dev}, time={header.timestamp}\n")
            continue


        # =====================================================
        # INIT PACKET
        # =====================================================
        if header.msg_type == 2:
            print(f"[SERVER] INIT from {dev}, time={header.timestamp}\n")
            continue


        # =====================================================
        # DATA PACKET
        # =====================================================
        if header.msg_type == 1:

            cpu_start = time.process_time()

            # -------------------------------------------------
            # SEND ACK IF DANGER PACKET
            # -------------------------------------------------
            if header.flags == 1:
                try:
                    ack = (1).to_bytes(1, "big")
                    server_socket.sendto(ack, address)
                    time.sleep(3)
                    print(f"[SERVER] Sent ACK to device {dev}")
                except Exception as e:
                    print(f"[SERVER] Failed to send ACK: {e}")

            # -------------------------------------------------
            # SEQUENCE TRACKING (duplicates & gaps)
            # -------------------------------------------------
            if dev in last_seq:
                if seq == last_seq[dev]:
                    duplicate_flag = 1
                    dup_count += 1
                    continue
                elif seq > last_seq[dev] + 1:
                    gap_flag = 1
                    loss_count += 1

            last_seq[dev] = seq

            # Decode payload value
            payload = packet[Header.Size:]
            value = struct.unpack('!H',payload)[0]

            # Update metrics
            packet_count += 1
            bytes_total += len(packet)

            print(f"[SERVER] DATA from {dev} seq={seq}, value={value}, "
                  f"time={header.timestamp}, danger_flag={header.flags}\n")

            # Create buffer if missing
            if dev not in buffers:
                buffers[dev] = []

            packet_entry = (
                header.timestamp,  # 0 timestamp (sorting)
                seq,               # 1 seq
                value,             # 2 value
                duplicate_flag,    # 3 duplicate
                gap_flag,          # 4 gap
                arrival_time       # 5 arrival time
            )

            # Add to buffer and sort
            buffers[dev].append(packet_entry)
            buffers[dev].sort(key=lambda x: x[0])

            # CPU tracking
            cpu_end = time.process_time()
            cpu_counts += 1
            cpu_total_time += (cpu_end - cpu_start)

            # -------------------------------------------------
            # FLUSH FROM BUFFER WHEN TOO LARGE
            # -------------------------------------------------
            if len(buffers[dev]) > BUFFER_THRESHOLD:
                oldest = buffers[dev].pop(0)
                writer.writerow([
                    dev,
                    oldest[1],  # seq
                    oldest[0],  # timestamp
                    oldest[2],  # value
                    oldest[3],  # duplicate flag
                    oldest[4],  # gap flag
                    oldest[5],  # arrival time
                ])
                temp_csv.flush()

# =====================================================
# FLUSH REMAINING BUFFERS
# =====================================================
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
            pkt[5],  # arrival_time
        ])

# =====================================================
# METRICS
# =====================================================
if packet_count > 0:
    avg_bytes = bytes_total / packet_count
    print(f"[METRIC] bytes_per_report = {avg_bytes:.2f} bytes\n")
    print(f"[METRIC] packets_received = {packet_count}\n")
    print(f"[METRIC] Packets lost = {loss_count}\n")
    print(f"[METRIC] packets duplicated = {dup_count}\n")
    print(f"[METRIC] CPU_MS_PER_REPORT = {(cpu_total_time / cpu_counts) * 1000}\n")
else:
    print("[METRIC] No packets received.\n")

temp_csv.close()
server_socket.close()
print("[SERVER] Shutdown complete.\n")
