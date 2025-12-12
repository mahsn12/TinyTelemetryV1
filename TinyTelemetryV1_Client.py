# TinyTelemetryV1_Client.py
import socket as skt
from headers import Header
import threading, time, struct
from globals import client_IP, client_port, server_IP, server_port
from Client import Client
import random
import sys

# -------------------------
# Run duration
# -------------------------
RUN_DURATION = 50
start_time = time.time()
# Helpers
# -------------------------
def custom_random():
    return random.randint(51,110) if random.random() < 0.10 else random.randint(1,50)

def maybe_recv_ack(sock, expected_addr, timeout=8):
    """Receive ack with timeout; returns True if valid ack received."""
    sock.settimeout(timeout)
    try:
        ack_packet, addr = sock.recvfrom(1024)
        if addr == expected_addr:
            ack_value = int.from_bytes(ack_packet, "big")
            return ack_value == 1
    except skt.timeout:
        return False
    except Exception:
        return False
    finally:
        sock.settimeout(None)

# -------------------------
# Threads
# -------------------------
def send_heartbeat(client_obj):
    time.sleep(5)
    while (time.time() - start_time < RUN_DURATION):
        header = Header(device_id=client_obj.device_id, msg_type=0)
        hb_packet = header.heartbeat()
        try:
            client_obj.sock.sendto(hb_packet, (server_IP, server_port))
        except Exception:
            break
        print(f"[CLIENT {client_obj.device_id}] Sent HEARTBEAT")
        # sleep in 1s increments but stop if duration expired
        for _ in range(30):
            if time.time() - start_time >= RUN_DURATION:
                break
            time.sleep(1)

def client_thread(client_obj):
    seq_num = 0

    # INIT
    try:
        init_header = Header(device_id=client_obj.device_id, msg_type=2)
        init_packet = init_header.Pack_Init()
        client_obj.sock.sendto(init_packet, (server_IP, server_port))
        print(f"[INFO] Client {client_obj.device_id} sent INIT")
    except Exception as e:
        print(f"[CLIENT {client_obj.device_id}] INIT send error: {e}")

    time.sleep(2)

    hb_thread = threading.Thread(target=send_heartbeat, args=(client_obj,), daemon=True)
    hb_thread.start()

    # DATA LOOP
    while (time.time() - start_time < RUN_DURATION):
        try:
            data = custom_random()
            danger_flag = 0 if data < 60 else 1

            header = Header(
                device_id=client_obj.device_id,
                seq_num=seq_num,
                flags=danger_flag,
                msg_type=1
            )

            header_bytes = header.Pack_Message()
            data_bytes = struct.pack('!H', data)
            packet = header_bytes + data_bytes

            # send packet (may fail if socket closed)
            client_obj.sock.sendto(packet, (server_IP, server_port))

            # Only danger packets require ACK
            if danger_flag == 1:
                ack_received = False
                ack_start = time.time()

                while not ack_received and (time.time() - ack_start < 30) and (time.time() - start_time < RUN_DURATION):
                    # wait for ack with timeout
                    got = maybe_recv_ack(client_obj.sock, (server_IP, server_port), timeout=8)
                    if got:
                        print(f"[CLIENT {client_obj.device_id}] Valid ACK received")
                        ack_received = True
                        break
                    print(f"[CLIENT {client_obj.device_id}] Timeout. Resending danger packet.")
                    try:
                        client_obj.sock.sendto(packet, (server_IP, server_port))
                    except Exception:
                        # socket closed or error: break out
                        break

                if not ack_received:
                    print(f"[CLIENT {client_obj.device_id}] No ACK for 30 seconds. Giving up.")

            print(f"[CLIENT {client_obj.device_id}] Sent DATA seq={seq_num}, value={data}, flag={danger_flag}")

            seq_num += 1

            # sleep in small increments but stop early if duration expired
            for _ in range(4):
                if time.time() - start_time >= RUN_DURATION:
                    break
                time.sleep(1)

        except Exception as e:
            # If socket closed or other error during shutdown, just break
            # print(f"[CLIENT {client_obj.device_id}] Error in main loop: {e}")
            break

    # cleanup for this client thread
    try:
        client_obj.sock.close()
    except Exception:
        pass
    print(f"[CLIENT {client_obj.device_id}] Shutdown cleanly.")

# -------------------------
# Create clients & start threads
# -------------------------

c1 = Client(device_id=101, client_ip='127.0.0.1', client_port=0)
time.sleep(2)
c2 = Client(device_id=102, client_ip='127.0.0.1', client_port=0)
time.sleep(6)
c3 = Client(device_id=103, client_ip='127.0.0.1', client_port=0)

t1 = threading.Thread(target=client_thread, args=(c1,), daemon=True)
t2 = threading.Thread(target=client_thread, args=(c2,), daemon=True)
t3 = threading.Thread(target=client_thread, args=(c3,), daemon=True)

t1.start()
t2.start()
t3.start()

# keep main alive until run duration expires
try:
    while time.time() - start_time < RUN_DURATION:
        time.sleep(1)
except KeyboardInterrupt:
    pass

# give threads a moment to finish
time.sleep(1)
print("[aCLIENTS] Run duration complete. Exiting.")
sys.exit(0)
