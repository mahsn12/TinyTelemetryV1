# IoT UDP Telemetry System (Client–Server)

A lightweight IoT telemetry system built with **UDP sockets** in Python.  
Designed for IoT-style devices that send:

- **INIT packet**
- **Periodic HEARTBEAT packets**
- **Telemetry DATA packets**

The server receives all packets, decodes a **custom binary header**, logs payloads, detects **duplicates and sequence gaps**, and writes structured output into a CSV file.

---

## ⚙️ Requirements

- Python 3.8+
- Runs on Linux or Windows (WSL recommended)
- Uses only Python standard libraries (`socket`, `csv`, `struct`, `threading`, etc.)

---

## 🚀 Run Instructions (Using WSL)

### 1 — Open WSL
wsl

### 2 — Navigate to project folder (change path as needed)
cd /mnt/c/Users/YourName/Desktop/project

### 3 — (Optional) Create virtual environment
python3 -m venv venv  
source venv/bin/activate  

### 4 — Start Script 
wsl  
cd /mnt/c/Users/YourName/Desktop/project  
bash Run.sh

---

## ✅ Expected System Behavior

| Component | Action |
|---|---|
| Client | Sends INIT → then heartbeats every 30s → sends data every 6s |
| Server | Decodes packets, prints logs, detects duplicates + missing sequences, exports CSV |

---

## 📊 Generated CSV Format (temp.csv)

device_id, seq_num, timestamp, msg_type, value, duplicate_flag, gap_flag, arrival_time

---



## 🧠 Design Decisions & Mechanisms

### 1. Custom Binary Header (Efficient)
Uses fixed-size struct for minimal packet overhead:
Format = '!HIIBB'

| Field | Bytes | Purpose |
|---|---:|---|
| device_id | 2 | Identifies device |
| seq_num | 4 | Detects order, loss, duplicates |
| timestamp | 4 | Packet creation time |
| msg_type | 1 | 0=heartbeat, 1=data, 2=init |
| flags | 1 | Extra state metadata |

Advantages:
- Small size
- Fast parsing
- IoT optimized
- No text serialization overhead

---

### 2. UDP Instead of TCP
✔ Low latency  
✔ No connection handshake  
✔ Best for continuous IoT telemetry  
✖ No delivery guarantee → solved via sequence tracking  

---

### 3. Packet Loss & Duplicate Detection
If seq == last_seq → duplicate  
If seq > last_seq + 1 → gap (packet loss)

Implemented per-device using a dictionary:
last_seq[device_id] = seq

---

### 4. Heartbeat Runs in Background
threading.Thread(target=send_heartbeat, daemon=True).start()

Ensures heartbeats are sent independently and never block data transmission.

---

### 5. Real-Time CSV Logging
writer.writerow(...)  
temp_csv.flush()  

Data is written instantly to disk to prevent loss on shutdown.

---

### 6. Shutdown Metrics
When the server stops, it prints:

- Packets received
- Packet loss count
- Duplicates count
- Average packet size

---



## 🏁 Summary

This system provides a real IoT telemetry simulation with:

✅ Binary protocol  
✅ UDP transmission  
✅ Heartbeats + sensor data  
✅ Loss & duplicate detection  
✅ Structured CSV logging  
✅ Multithreading  

---
