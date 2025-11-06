#!/bin/bash
echo "🚀 Starting Tiny Telemetry Phase 1 test..."

# Trap Ctrl+C and forward SIGINT to children (instead of killing immediately)
trap "echo -e '\n🛑 Stopping all processes...'; kill -SIGINT $CLIENT_PID $SERVER_PID; wait; exit" INT

python3 TinyTelemetryV1_Client.py &
CLIENT_PID=$!

sleep 1

python3 TinyTelemetryV1_Server.py &
SERVER_PID=$!

wait
