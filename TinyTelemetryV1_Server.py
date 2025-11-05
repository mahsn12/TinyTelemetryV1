import socket as skt
from headers import Header
import time , threading , csv
from globals import client_IP,client_port,server_IP,server_port


server_socket = skt.socket(family=skt.AF_INET, type=skt.SOCK_DGRAM)
clients = {}

temp_csv = open('temp.csv', 'w', newline='')
writer = csv.writer(temp_csv)
writer.writerow('device_id','seq_num','timestamp','msg_type','decode')
def check_heartbeat():
    while True:
        timer = time.time()
        for adress,last in list(clients.items()):
            if timer-last >= 10:
                header = Header()
                hb_packet = header.heartbeat()
                server_socket.sendto(hb_packet,(client_IP,client_port))
                print("💓 Heartbeat Sent to device",address)
                clients[address]=timer

threading.Thread(target=check_heartbeat,daemon=True).start()
server_socket.bind((server_IP, server_port))
print(f"🟢 Server is listening on {server_IP}:{server_port}")

while True:
    packet,address=server_socket.recvfrom(1024)#data is the packet
    if len(packet)< Header.Size:
        print("Wrong Packet Size")
        continue

    clients[address]=time.time()    
    header = Header()
    header.unPack(packet[:Header.Size])#[start:end]
    header.show()
    payload = packet[Header.Size:]
    print("PayLoad: "+payload.decode())
    writer.writerow([header.device_id,header.seq_num,header.timestamp,header.msg_type,payload.decode()])


