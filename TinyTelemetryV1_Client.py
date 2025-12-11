import socket as skt
from headers import Header
import threading, time, struct
from globals import client_IP, client_port, server_IP, server_port
from Client import Client
import random


def custom_random():
    return random.randint(51,110) if random.random() < 0.10 else random.randint(1,50)


def send_heartbeat(client_obj):
    time.sleep(5)
    while True:
        header = Header(device_id=client_obj.device_id, msg_type=0)
        hb_packet = header.heartbeat()
        client_obj.sock.sendto(hb_packet, (server_IP, server_port))
        print(f"[CLIENT {client_obj.device_id}] Sent HEARTBEAT")
        time.sleep(30)


def client_thread(Client_obj):
    seq_num = 0

    # -------------------- INIT MESSAGE --------------------
    init_header = Header(device_id=Client_obj.device_id, msg_type=2)
    init_packet = init_header.Pack_Init()
    Client_obj.sock.sendto(init_packet, (server_IP, server_port))
    print(f"[INFO] Client {Client_obj.device_id} sent INIT")
    # ------------------------------------------------------

    time.sleep(2)

    # Start heartbeat thread
    threading.Thread(target=send_heartbeat, args=(Client_obj,), daemon=True).start()

    # -------------------- DATA LOOP -----------------------
    while True:
        data = custom_random()
        danger_flag = 0 if data < 60 else 1

        header = Header(
            device_id=Client_obj.device_id,
            seq_num=seq_num,
            flags=danger_flag,
            msg_type=1
        )

        header_bytes = header.Pack_Message()
        data_bytes = struct.pack('!H', data)

        packet = header_bytes + data_bytes

        Client_obj.sock.sendto(packet, (server_IP, server_port))
        print(f"[CLIENT {Client_obj.device_id}] Sent DATA seq={seq_num}, value={data}, flag={danger_flag}")

        seq_num += 1
        time.sleep(6)
    # ------------------------------------------------------


# -------- CREATE CLIENT OBJECTS --------
c1 = Client(device_id=101, client_ip='127.0.0.1', client_port=0)
c2 = Client(device_id=102, client_ip='127.0.0.1', client_port=0)
c3 = Client(device_id=103, client_ip='127.0.0.1', client_port=0)


# -------- START THREADS PROPERLY --------
threading.Thread(target=client_thread, args=(c1,), daemon=True).start()
threading.Thread(target=client_thread, args=(c2,), daemon=True).start()
threading.Thread(target=client_thread, args=(c3,), daemon=True).start()

# Keep main thread alive
while True:
    time.sleep(1)
