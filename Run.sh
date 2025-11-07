#!/bin/bash
echo "🚀 Starting Tiny Telemetry Phase 1 test..."

cleanup() {
    echo -e "\n🛑 Stopping all processes gracefully..."

    kill -INT $CLIENT_PID 2>/dev/null
    kill -INT $SERVER_PID 2>/dev/null

    # give them time to reach finally block
    sleep 2

    # force kill if still running (only if needed)
    kill -TERM $CLIENT_PID 2>/dev/null
    kill -TERM $SERVER_PID 2>/dev/null

    wait $CLIENT_PID 2>/dev/null
    wait $SERVER_PID 2>/dev/null

    echo -e "✅ All processes stopped."
    exit 0
}

trap cleanup INT TERM

# Run server and client
python3 TinyTelemetryV1_Server.py &
SERVER_PID=$!

sleep 1

python3 TinyTelemetryV1_Client.py &
CLIENT_PID=$!

# Auto shutdown after 30 seconds
sleep 30
echo -e "\n⏳ 30 seconds passed... triggering shutdown..."

cleanup
