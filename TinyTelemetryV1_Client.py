import socket as skt
from headers import Header
import threading, time, struct, os, random, sys
from globals import server_IP, server_port, client_IP
from Client import Client
from collections import deque
import heapq

RUN_DURATION = int(os.getenv("RUN_DURATION", 50))
start_time = time.time()

SIMULATE_NETEM = os.getenv("SIMULATE_NETEM", "0") == "1"
SIMULATE_LOSS = float(os.getenv("SIMULATE_LOSS", "0"))
SIMULATE_DELAY_MS = float(os.getenv("SIMULATE_DELAY_MS", "0"))
SIMULATE_JITTER_MS = float(os.getenv("SIMULATE_JITTER_MS", "0"))

reorder_buffer = deque()
reorder_lock = threading.Lock()

# Scheduler queue for delayed sends: list of (send_time, seq, packet, addr)
send_queue = []
send_queue_lock = threading.Lock()

# Server liveness flag
SERVER_ALIVE = True

# start a background thread to flush scheduled sends
def _sender_thread(sock):
    while True:
        now = time.time()
        to_send = None
        with send_queue_lock:
            if send_queue and send_queue[0][0] <= now:
                send_time, seq, packet, addr = heapq.heappop(send_queue)
                to_send = (packet, addr, seq)
        if to_send:
            p, a, s = to_send
            try:
                sock.sendto(p, a)
                # indicate release from netem scheduler
                print(f"[NETEM RELEASE] seq={s} sent to {a}")
            except Exception:
                pass
            continue
        time.sleep(0.01)

# We'll start the sender thread lazily when first needed
_sender_started = False


def custom_random():
    return random.randint(51, 110) if random.random() < 0.10 else random.randint(1, 50)


def maybe_recv_ack(sock, expected_addr, expected_seq=None, timeout=1.0):
    prev = sock.gettimeout()
    sock.settimeout(timeout)
    try:
        pkt, a = sock.recvfrom(1024)
        if a != expected_addr:
            return False
        if len(pkt) >= 5:
            t = pkt[0]
            seq = struct.unpack('!I', pkt[1:5])[0]
            return t == 1 and (expected_seq is None or seq == expected_seq)
        return False
    except Exception:
        return False
    finally:
        sock.settimeout(prev)


def maybe_recv_alive(sock, expected_addr, timeout=5.0):
    prev = sock.gettimeout()
    sock.settimeout(timeout)
    try:
        pkt, a = sock.recvfrom(1024)
        if a != expected_addr:
            return False
        if len(pkt) >= 1:
            t = pkt[0]
            return t == 4
        return False
    except Exception:
        return False
    finally:
        sock.settimeout(prev)


def netem_send(sock, packet, addr, seq=None):
    """Send or schedule a send. Returns True if sent or scheduled, False if dropped."""
    global _sender_started
    # Simulated loss
    if SIMULATE_NETEM and SIMULATE_LOSS > 0 and random.random() < SIMULATE_LOSS:
        print(f"[SIM NETEM] DROPPED seq={seq}")
        return False

    # If not simulating delay, send immediately
    if not (SIMULATE_NETEM and SIMULATE_DELAY_MS > 0 and seq is not None):
        try:
            sock.sendto(packet, addr)
            return True
        except Exception:
            return False

    # Ensure sender thread running
    if not _sender_started:
        t = threading.Thread(target=_sender_thread, args=(sock,), daemon=True)
        t.start()
        _sender_started = True

    # Compute target send time using base delay + jitter
    jitter = random.uniform(-SIMULATE_JITTER_MS, SIMULATE_JITTER_MS)
    delay_ms = SIMULATE_DELAY_MS + jitter
    # occasional reordering by increasing delay for this packet
    if random.random() < 0.3:
        delay_ms += random.uniform(0, SIMULATE_DELAY_MS * 2)

    send_time = time.time() + max(0.0, delay_ms / 1000.0)

    with send_queue_lock:
        heapq.heappush(send_queue, (send_time, seq if seq is not None else 0, packet, addr))

    # log that packet was scheduled (held)
    print(f"[NETEM SCHEDULE] seq={seq} delay_ms={delay_ms:.1f} target={send_time:.3f}")
    return True


def send_heartbeat(client):
    global SERVER_ALIVE
    time.sleep(5)
    missed = 0
    while time.time() - start_time < RUN_DURATION and SERVER_ALIVE:
        hb = Header(device_id=client.device_id, msg_type=0).heartbeat()
        netem_send(client.sock, hb, (server_IP, server_port))
        # wait for server alive reply
        alive = maybe_recv_alive(client.sock, (server_IP, server_port), timeout=5.0)
        if not alive:
            missed += 1
            print(f"[CLIENT {client.device_id}] Missed heartbeat reply {missed}")
            if missed >= 3:
                print(f"[CLIENT {client.device_id}] Server appears down — stopping client threads")
                SERVER_ALIVE = False
                break
        else:
            missed = 0
        time.sleep(30)


def client_thread(client):
    seq = 0

    init = Header(device_id=client.device_id, msg_type=2).Pack_Init()
    netem_send(client.sock, init, (server_IP, server_port))
    print(f"[CLIENT {client.device_id}] INIT sent")

    threading.Thread(target=send_heartbeat, args=(client,), daemon=True).start()

    while time.time() - start_time < RUN_DURATION and SERVER_ALIVE:
        value = custom_random()
        danger = 1 if value >= 60 else 0

        h = Header(device_id=client.device_id, seq_num=seq, msg_type=1, flags=(1 if danger else 0))
        pkt = h.Pack_Message() + struct.pack("!H", value)

        sent = netem_send(client.sock, pkt, (server_IP, server_port), seq)

        if danger:
            attempts = 0
            timeout = 1.0
            max_attempts = 5
            while attempts < max_attempts and time.time() - start_time < RUN_DURATION:
                got = maybe_recv_ack(client.sock, (server_IP, server_port), expected_seq=seq, timeout=timeout)
                if got:
                    print(f"[CLIENT {client.device_id}] ACK seq={seq}")
                    break
                attempts += 1
                timeout = min(4.0, timeout * 2)
                sent = netem_send(client.sock, pkt, (server_IP, server_port), seq)
            else:
                print(f"[CLIENT {client.device_id}] WARNING: no ACK for seq={seq} after {attempts} attempts")

        # Log only when packet was actually sent/scheduled
        if sent:
            print(f"[CLIENT {client.device_id}] DATA seq={seq} val={value} danger={danger}")
        seq += 1
        time.sleep(4)

    try:
        client.sock.close()
    except Exception:
        pass
    print(f"[CLIENT {client.device_id}] Shutdown cleanly")


clients = [
    Client(101, client_IP, 0),
    Client(102, client_IP, 0),
    Client(103, client_IP, 0),
]

for c in clients:
    threading.Thread(target=client_thread, args=(c,), daemon=True).start()
    time.sleep(0.5)

try:
    while time.time() - start_time < RUN_DURATION and SERVER_ALIVE:
        time.sleep(1)
except KeyboardInterrupt:
    pass

if not SERVER_ALIVE:
    print("Server detected down — exiting client process")

sys.exit(0)
