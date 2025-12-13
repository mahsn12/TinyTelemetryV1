import socket as skt
from headers import Header
import csv, time, struct, os
from globals import server_IP, server_port

RUN_DURATION = int(os.getenv("RUN_DURATION", 62))

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
temp_csv = open('temp.csv', 'w', newline='')
writer = csv.writer(temp_csv)
writer.writerow([
    'device_id', 'seq_num', 'timestamp', 'value',
    'duplicate_flag', 'gap_flag', 'arrival_time'
])

# -------------------------
# Metrics
# -------------------------
packet_count = 0
bytes_total = 0
# duplicate metrics: total duplicate packet arrivals, and number of distinct seqs that experienced duplication
dup_total = 0
dup_seq_count = 0
dup_seq_seen = {}  # dev -> set(seq)
loss_count = 0

written_count = 0

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

    # If already written this seq -> duplicate
    if seq <= last_written[dev]:
        duplicate_flag = 1
        # mark duplicate totals and per-seq
        dup_total += 1
        if dev not in dup_seq_seen:
            dup_seq_seen[dev] = set()
        if seq not in dup_seq_seen[dev]:
            dup_seq_seen[dev].add(seq)
            dup_seq_count += 1
        # duplicate received; ignore for writing
        continue

    # If already in buffer -> duplicate
    if any(p[0] == seq for p in buffers[dev]):
        duplicate_flag = 1
        dup_total += 1
        if dev not in dup_seq_seen:
            dup_seq_seen[dev] = set()
        if seq not in dup_seq_seen[dev]:
            dup_seq_seen[dev].add(seq)
            dup_seq_count += 1
        continue

    # store packet in list buffer
    value = struct.unpack('!H', packet[Header.Size:])[0]
    buffers[dev].append((seq, header.timestamp, value, arrival_time))

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
                written_count += 1
                bytes_total += (Header.Size + 2)
                last_written[dev] = seq_b
                expected = seq_b + 1
            else:
                # in-order packet
                writer.writerow([dev, seq_b, ts_b, val_b, duplicate_flag, gap_flag, at_b])
                temp_csv.flush()
                written_count += 1
                bytes_total += (Header.Size + 2)
                last_written[dev] = seq_b
                expected += 1

    cpu_end = time.process_time()
    cpu_counts += 1
    cpu_total_time += (cpu_end - cpu_start)

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
                written_count += 1
                bytes_total += (Header.Size + 2)
                last_written[dev] = seq_b
                expected = seq_b + 1
            else:
                writer.writerow([dev, seq_b, ts_b, val_b, duplicate_flag, gap_flag, at_b])
                temp_csv.flush()
                written_count += 1
                bytes_total += (Header.Size + 2)
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
                written_count += 1
                bytes_total += (Header.Size + 2)
                last_written[dev] = seq_b
                expected = seq_b + 1
            else:
                writer.writerow([dev, seq_b, ts_b, val_b, duplicate_flag, gap_flag, at_b])
                temp_csv.flush()
                written_count += 1
                bytes_total += (Header.Size + 2)
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

# =====================================================
# Metrics
# =====================================================
print("\n[METRICS]")
# compute losses per-device using highest-seen sequence minus last_written
for dev in set(list(max_seq_seen.keys()) + list(last_written.keys())):
    max_seen = max_seq_seen.get(dev, -1)
    last_w = last_written.get(dev, -1)

    # sequences that should exist
    expected_seqs = set(range(last_w + 1, max_seen + 1))

    # sequences that actually arrived but are still buffered
    buffered_seqs = set(seq for seq, *_ in buffers.get(dev, []))

    # lost = expected but neither written nor buffered
    lost_seqs = expected_seqs - buffered_seqs

    loss_count += len(lost_seqs)

print(f"Packets written: {written_count}")
print(f"Packets lost: {loss_count}")
print(f"Duplicate packets (total arrivals): {dup_total}")
print(f"Duplicate sequences: {dup_seq_count}")
print(f"Avg bytes: {bytes_total / max(written_count,1):.2f}")
print(f"CPU_MS_PER_REPORT = {(cpu_total_time / max(cpu_counts,1)) * 1000:.3f}")

