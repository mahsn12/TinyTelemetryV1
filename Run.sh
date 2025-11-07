#!/bin/bash
echo "🚀 Starting Tiny Telemetry Phase 1 test..."

cleanup() {
    echo -e "\n🛑 Stopping all processes gracefully..."

    # Send CTRL+C (INT) instead of killing instantly
    kill -INT $CLIENT_PID 2>/dev/null
    kill -INT $SERVER_PID 2>/dev/null

    # Wait for them to exit normally
    wait $CLIENT_PID 2>/dev/null
    wait $SERVER_PID 2>/dev/null

    echo -e "✅ All processes stopped."
    exit 0
}

trap cleanup INT TERM

python3 TinyTelemetryV1_Server.py &
SERVER_PID=$!

sleep 1

python3 TinyTelemetryV1_Client.py &
CLIENT_PID=$!

wait $SERVER_PID
wait $CLIENT_PID
