import struct 
import time

class Header:
    Format ='!HIIBB'
    Size = struct.calcsize(Format)

    def __init__(self, device_id=0, seq_num=0, msg_type=1, flags=0, timestamp=None):#const in pyhton must be called __init__
        self.device_id = device_id
        self.seq_num = seq_num
        self.msg_type = msg_type
        self.flags = flags
        # Use provided timestamp if given, otherwise current time
        if timestamp is None:
            self.timestamp = int(time.time())
        else:
            try:
                self.timestamp = int(timestamp)
            except Exception:
                self.timestamp = int(time.time())

    def Pack_Message(self):
        return struct.pack(
            self.Format,
            self.device_id,
            self.seq_num,
            self.timestamp,
            self.msg_type,#message type
            self.flags
             )
    

    def unPack(self, packet):  # data is the packet you need to unpack
        values = struct.unpack(self.Format, packet) 
        self.device_id = values[0]
        self.seq_num = values[1]
        self.timestamp = values[2]
        self.msg_type = values[3]
        self.flags = values[4]

    def show(self):
        print("Device ID:", self.device_id)
        print("Seq Num:", self.seq_num)
        print("Timestamp:", self.timestamp)
        print("Msg Type:", self.msg_type)
        print("Flags:", self.flags)

    def heartbeat(self):
        return struct.pack(Header.Format,
            self.device_id,
            self.seq_num,
            self.timestamp,
            0,#message type
            self.flags                
            )

    def Pack_Init(self):
        return struct.pack(
        Header.Format,
        self.device_id,
        self.seq_num,
        self.timestamp,
        2,#message type
        self.flags 
        )
