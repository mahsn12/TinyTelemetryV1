# TinyTelemetryV1_Client

A Python-based telemetry client-server system that allows devices to send structured packets to a server for logging and processing. This project demonstrates basic packet creation, sending over UDP, and server-side reception with optional header fields.

---

## 🧩 Project Overview

This project is divided into a client and a server:

- **Client (`TinyTelemetryV1_Client.py`)**  
  Sends telemetry packets with structured headers including:
  - Device ID
  - Sequence number
  - Message type
  - Flags
  - Timestamp

- **Server (`TinyTelemetryV1_Server.py`)**  
  Listens for incoming telemetry packets, unpacks them, and optionally logs the data to a CSV file.

- **Header Module (`headers.py`)**  
  Defines the packet structure and handles packing/unpacking using Python's `struct` module.

- **Globals (`globals.py`)**  
  Stores global configuration such as server IP, port, and optional flags.

- **Temporary Storage (`temp.csv`)**  
  Example output for received telemetry data.

---

## 🚀 Features

- Sends structured binary packets over UDP
- Configurable packet headers
- Optional fields like flags and checksum for extended functionality
- Modular structure for easy extension and customization
- Logging of telemetry data for analysis

---

## ⚙️ Installation

1. **Clone the repository**
```bash
git clone https://github.com/mahsn12/TinyTelemetryV1_Client.git
cd TinyTelemetryV1_Client
