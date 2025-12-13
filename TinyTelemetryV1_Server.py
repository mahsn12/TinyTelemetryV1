import socket as skt
from headers import Header
import csv, time, struct, os
from globals import server_IP, server_port
import matplotlib.pyplot as plt

RUN_DURATION = int(os.getenv("RUN_DURATION", 75))


snapshot_points = [10, 30, 60]
snapshots_taken = set()

snap_time = []
snap_bytes = []
snap_dup_rate = []
snap_loss = []
snap_cpu = []

# -------------------------
# Socket setup
# -------------------------
server_socket = skt.socket(skt.AF_INET, skt.SOCK_DGRAM)
server_socket.bind((server_IP, server_port))
server_socket.settimeout(0.5)

print(f"[SERVER] Listening on UDP {server_IP}:{server_port}")

# -------------------------
# CSV setup
# -------------------------
# CSV path: allow override via PACKETS_CSV env var. If opening fails, fall back to /tmp
csv_path = os.getenv('PACKETS_CSV', 'temp.csv')
try:
    csv_dir = os.path.dirname(csv_path)
    if csv_dir:
        os.makedirs(csv_dir, exist_ok=True)
    temp_csv = open(csv_path, 'w', newline='')
except Exception:
    # fallback to /tmp/<project>/tests/packets.csv
    fallback_base = os.path.join('/tmp', os.path.basename(os.getcwd()))
    try:
        os.makedirs(os.path.join(fallback_base, 'tests'), exist_ok=True)
    except Exception:
        pass
    csv_path = os.path.join(fallback_base, 'tests', os.path.basename(csv_path) or 'packets.csv')
    try:
        temp_csv = open(csv_path, 'w', newline='')
    except Exception:
        # last resort: open in current dir (may raise)
        temp_csv = open('temp.csv', 'w', newline='')
writer = csv.writer(temp_csv)
writer.writerow([
    'device_id', 'seq_num', 'timestamp', 'value',
    'duplicate_flag', 'gap_flag', 'arrival_time'
])
print(f"[SERVER] Writing packets CSV to: {csv_path}")

# -------------------------
# Metrics
# -------------------------
# packets_received: number of unique DATA packets accepted (not duplicate packets)
packets_received = 0
# total bytes across accepted packets (for bytes_per_report)
packets_bytes_total = 0
# duplicate metrics: total duplicate packet arrivals, and number of distinct seqs that experienced duplication
dup_total = 0
dup_seq_count = 0
dup_seq_seen = {}  # dev -> set(seq)
loss_count = 0

# readings_written: total number of individual readings written to CSV (after batching)
readings_written = 0

cpu_counts = 0
cpu_total_time = 0

# -------------------------
# Tracking
# -------------------------
last_seq = {}
last_written = {}
buffers = {}
BUFFER_THRESHOLD = 5
max_seq_seen = {}

start_time = time.time()

# =====================================================
# Main loop
# =====================================================
while time.time() - start_time < RUN_DURATION:
    try:
        packet, address = server_socket.recvfrom(1024)
    except skt.timeout:
        continue

    if len(packet) < Header.Size:
        continue

    header = Header()
    header.unPack(packet[:Header.Size])
    arrival_time = time.time()

    dev = header.device_id
    seq = header.seq_num

    # track highest sequence seen for this device
    max_seq_seen[dev] = max(seq, max_seq_seen.get(dev, -1))

    # -------------------------
    # HEARTBEAT
    # -------------------------
    if header.msg_type == 0:
        print(f"[SERVER] HEARTBEAT from {dev}")
        # reply to heartbeat so clients can detect server liveness
        try:
            alive = struct.pack('!B', 4)
            server_socket.sendto(alive, address)
        except Exception:
            pass
        continue

    # -------------------------
    # INIT
    # -------------------------
    if header.msg_type == 2:
        print(f"[SERVER] INIT from {dev}")
        continue

    # -------------------------
    # DATA
    # -------------------------
    cpu_start = time.process_time()

    # initialize per-device structures
    if dev not in buffers:
        buffers[dev] = []  # list of (seq, timestamp, value, arrival_time)
    if dev not in last_written:
        last_written[dev] = -1

    duplicate_flag = 0
    gap_flag = 0

    # parse payload into one or more readings (batch support)
    payload = packet[Header.Size:]
    num_readings = max(1, len(payload) // 2)
    readings = []
    for i in range(num_readings):
        start = i * 2
        value = struct.unpack('!H', payload[start:start+2])[0]
        seq_i = seq + i
        readings.append((seq_i, header.timestamp, value, arrival_time))

    # classify readings: detect duplicates and collect new readings
    new_readings = []
    for seq_i, ts_i, val_i, at_i in readings:
        if seq_i <= last_written[dev]:
            # already written -> duplicate arrival
            dup_total += 1
            if dev not in dup_seq_seen:
                dup_seq_seen[dev] = set()
            if seq_i not in dup_seq_seen[dev]:
                dup_seq_seen[dev].add(seq_i)
                dup_seq_count += 1
            continue
        if any(p[0] == seq_i for p in buffers[dev]):
            # already buffered -> duplicate arrival
            dup_total += 1
            if dev not in dup_seq_seen:
                dup_seq_seen[dev] = set()
            if seq_i not in dup_seq_seen[dev]:
                dup_seq_seen[dev].add(seq_i)
                dup_seq_count += 1
            continue
        new_readings.append((seq_i, ts_i, val_i, at_i))

    # accept packet only if it contains at least one new reading
    if new_readings:
        buffers[dev].extend(new_readings)
        packets_received += 1
        packets_bytes_total += len(packet)

    # send ACK if requested (type 1 + seq32)
    if header.flags == 1:
        try:
            ack = struct.pack('!BI', 1, seq)
            server_socket.sendto(ack, address)
        except Exception:
            pass

    # count writing later when the packet is flushed to CSV

    # process batch when we have at least 10 packets buffered for this device
    if len(buffers[dev]) >= 10:
        # reorder by sender timestamp
        batch = sorted(buffers[dev], key=lambda x: x[1])
        buffers[dev] = []
        expected = last_written.get(dev, -1) + 1
        for seq_b, ts_b, val_b, at_b in batch:
            duplicate_flag = 0
            gap_flag = 0
            if seq_b < expected:
                # already written -> duplicate arrival
                duplicate_flag = 1
                dup_total += 1
                if dev not in dup_seq_seen:
                    dup_seq_seen[dev] = set()
                if seq_b not in dup_seq_seen[dev]:
                    dup_seq_seen[dev].add(seq_b)
                    dup_seq_count += 1
            elif seq_b > expected:
                # gap detected, count missing as loss
                missing = seq_b - expected
                loss_count += missing
                gap_flag = 1
                # write the packet and advance
                writer.writerow([dev, seq_b, ts_b, val_b, duplicate_flag, gap_flag, at_b])
                temp_csv.flush()
                readings_written += 1
                last_written[dev] = seq_b
                expected = seq_b + 1
            else:
                # in-order packet
                writer.writerow([dev, seq_b, ts_b, val_b, duplicate_flag, gap_flag, at_b])
                temp_csv.flush()
                readings_written += 1
                last_written[dev] = seq_b
                expected += 1

    cpu_end = time.process_time()
    cpu_counts += 1
    cpu_total_time += (cpu_end - cpu_start)
    elapsed = int(time.time() - start_time)

    for t in snapshot_points:
        if elapsed >= t and t not in snapshots_taken:
            snapshots_taken.add(t)

            cur_dup_rate = dup_total / max((readings_written + dup_total), 1)
            cur_bytes = packets_bytes_total / max(readings_written, 1)
            cur_cpu = (cpu_total_time / max(readings_written, 1)) * 1000

            snap_time.append(t)
            snap_bytes.append(cur_bytes)
            snap_dup_rate.append(cur_dup_rate)
            snap_loss.append(loss_count)
            snap_cpu.append(cur_cpu)

            print(f"[SNAPSHOT @ {t}s] bytes={cur_bytes:.2f}, dup={cur_dup_rate:.4f}, loss={loss_count}, cpu={cur_cpu:.3f}")

    # safety: if buffer grows excessively large, flush the earliest batch of 10 by arrival time
    if len(buffers[dev]) > BUFFER_THRESHOLD * 10:
        buffers[dev].sort(key=lambda x: x[3])
        batch = buffers[dev][:10]
        buffers[dev] = buffers[dev][10:]
        expected = last_written.get(dev, -1) + 1
        for seq_b, ts_b, val_b, at_b in batch:
            duplicate_flag = 0
            gap_flag = 0
            if seq_b < expected:
                duplicate_flag = 1
                dup_total += 1
                if dev not in dup_seq_seen:
                    dup_seq_seen[dev] = set()
                if seq_b not in dup_seq_seen[dev]:
                    dup_seq_seen[dev].add(seq_b)
                    dup_seq_count += 1
            elif seq_b > expected:
                missing = seq_b - expected
                loss_count += missing
                gap_flag = 1
                writer.writerow([dev, seq_b, ts_b, val_b, duplicate_flag, gap_flag, at_b])
                temp_csv.flush()
                readings_written += 1
                last_written[dev] = seq_b
                expected = seq_b + 1
            else:
                writer.writerow([dev, seq_b, ts_b, val_b, duplicate_flag, gap_flag, at_b])
                temp_csv.flush()
                readings_written += 1
                last_written[dev] = seq_b
                expected += 1

# =====================================================
# Final flush
# =====================================================
for dev in list(buffers.keys()):
    # buffers[dev] is a dict(seq -> (timestamp, value, arrival_time))
    if isinstance(buffers[dev], list):
        seqs = sorted(buffers[dev], key=lambda x: x[1])
        for seq_b, ts_b, val_b, at_b in seqs:
            duplicate_flag = 0
            gap_flag = 0
            expected = last_written.get(dev, -1) + 1
            if seq_b < expected:
                duplicate_flag = 1
                dup_total += 1
                if dev not in dup_seq_seen:
                    dup_seq_seen[dev] = set()
                if seq_b not in dup_seq_seen[dev]:
                    dup_seq_seen[dev].add(seq_b)
                    dup_seq_count += 1
            elif seq_b > expected:
                missing = seq_b - expected
                loss_count += missing
                gap_flag = 1
                writer.writerow([dev, seq_b, ts_b, val_b, duplicate_flag, gap_flag, at_b])
                temp_csv.flush()
                readings_written += 1
                last_written[dev] = seq_b
                expected = seq_b + 1
            else:
                writer.writerow([dev, seq_b, ts_b, val_b, duplicate_flag, gap_flag, at_b])
                temp_csv.flush()
                readings_written += 1
                last_written[dev] = seq_b
                expected += 1
    else:
        # legacy list handling (shouldn't occur) — keep old behavior
        buffers[dev].sort(key=lambda x: x[0])
        for pkt in buffers[dev]:
            writer.writerow([
                dev,
                pkt[1],
                pkt[0],
                pkt[2],
                pkt[3],
                pkt[4],
                pkt[5]
            ])
            elapsed = int(time.time() - start_time)

            elapsed = int(time.time() - start_time)



# =====================================================
# Metrics
# =====================================================
print("\n[METRICS]")
# packets_received: unique packets accepted
print(f"Packets received: {packets_received}")
print(f"Readings written: {readings_written}")
print(f"Packets lost: {loss_count}")
print(f"Duplicate packets (total arrivals): {dup_total}")
print(f"Duplicate sequences: {dup_seq_count}")
# duplicate_rate per spec: dup_total / (readings_written + dup_total)
dup_rate = dup_total / max((readings_written + dup_total), 1)
print(f"Duplicate rate: {dup_rate:.6f}")
# bytes per report (per reading)
bytes_per_report = packets_bytes_total / max(readings_written, 1)
print(f"Bytes per report: {bytes_per_report:.2f}")
print(f"CPU_MS_PER_REPORT = {(cpu_total_time / max(readings_written,1)) * 1000:.3f}")

print("----------------------------------------------------------")



# =====================================================
# Derived metric (REAL)
# =====================================================
cpu_ms_per_report = (cpu_total_time / max(readings_written, 1)) * 1000

# =====================================================
# 1) Bytes per Report
# =====================================================
plt.figure()
plt.bar(snap_time, snap_bytes)
plt.xlabel("Time (seconds)")
plt.ylabel("Bytes per Report")
plt.title("Bytes per Report vs Time")
plt.grid(True, axis='y')
plt.tight_layout()
plt.savefig("bytes_per_report_over_time.png")
plt.close()

plt.figure()
plt.bar(snap_time, snap_dup_rate)
plt.xlabel("Time (seconds)")
plt.ylabel("Duplicate Rate")
plt.title("Duplicate Rate vs Time")
plt.grid(True, axis='y')
plt.tight_layout()
plt.savefig("duplicate_rate_over_time.png")
plt.close()


plt.figure()
plt.bar(snap_time, snap_loss)
plt.xlabel("Time (seconds)")
plt.ylabel("Packets Lost")
plt.title("Packet Loss vs Time")
plt.grid(True, axis='y')
plt.tight_layout()
plt.savefig("packet_loss_over_time.png")
plt.close()



plt.figure()
plt.bar(snap_time, snap_cpu)
plt.xlabel("Time (seconds)")
plt.ylabel("CPU ms per Report")
plt.title("CPU Time per Report vs Time")
plt.grid(True, axis='y')
plt.tight_layout()
plt.savefig("cpu_ms_per_report_over_time.png")
plt.close()


