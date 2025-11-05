import socket as skt
from headers import Header
import threading,time
from globals import client_IP,client_port,server_IP,server_port

sequnce_number = 1

client_socket = skt.socket(family=skt.AF_INET, type=skt.SOCK_DGRAM)
client_socket.bind((client_IP,client_port))

print(f"🟢 Client ready on {client_IP}:{client_port}")
def listen_for_hb():
    while True:
        packet,address = client_socket.recvfrom(1024)
        header = Header()
        header.unPack(packet[:Header.Size])
        if header.msg_type == 0 :
             print("💓 Heartbeat received from server!")


threading.Thread(target=listen_for_hb,daemon=True).start()


while True:
    header = Header(
        device_id=101,
        seq_num=sequnce_number,
        flags=0
    )
    
    packet = header.Pack_Message()
    payload = b'25.6'
    packet+=payload
    client_socket.sendto(packet, (server_IP, server_port))
    print("📤 Sent:", packet, "to", server_IP, ":", server_port)
    sequnce_number+=1
    time.sleep(15)


    

