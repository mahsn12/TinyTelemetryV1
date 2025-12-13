import socket as skt

class Client:
    def __init__(self, device_id, client_ip, client_port):
        self.device_id = device_id
        self.client_ip = client_ip
        self.client_port = client_port

        # Create socket for this client
        self.sock = skt.socket(skt.AF_INET, skt.SOCK_DGRAM)
        self.sock.bind((client_ip, client_port))



    @staticmethod
    def create_client(ip, port, device_id):
        return Client(device_id, ip, port)



