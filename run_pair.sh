#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(pwd)"
TEST_DIR="$PROJECT_DIR/tests/manual_pair"
mkdir -p "$TEST_DIR"

SERVER_CMD="python3 -u TinyTelemetryV1_Server.py"
CLIENT_CMD="python3 -u TinyTelemetryV1_Client.py"
DURATION=${DURATION:-70}
IF=${IF:-eth0}

has_cmd(){ command -v "$1" >/dev/null 2>&1; }

# Start tcpdump if available
if has_cmd tcpdump; then
    echo "Starting tcpdump..."
    tcpdump -i "$IF" -w "$TEST_DIR/capture.pcap" udp > /dev/null 2>&1 &
    TCP_PID=$!
else
    echo "tcpdump not found; skipping capture."
    TCP_PID=0
fi

echo "Starting server..."
(cd "$PROJECT_DIR" && $SERVER_CMD 2>&1 | tee "$TEST_DIR/server.log") &
SERVER_PID=$!

SERVER_PORT=8888
echo "Waiting for server to bind UDP $SERVER_PORT..."
for i in {1..50}; do
    if has_cmd netstat; then
        if netstat -anu 2>/dev/null | grep -q ":$SERVER_PORT "; then
            echo "Server is listening."
            break
        fi
    else
        echo "netstat unavailable; skipping port wait."
        break
    fi
    sleep 0.2
done

echo "Starting client..."
(cd "$PROJECT_DIR" && $CLIENT_CMD 2>&1 | tee "$TEST_DIR/client.log") &
CLIENT_PID=$!

echo "Running for $DURATION seconds..."
sleep "$DURATION"

echo "Stopping processes..."

# DO NOT KILL SERVER/CLIENT — they will exit naturally (your requirement)
# Only stop tcpdump
if [ "$TCP_PID" -ne 0 ]; then
    kill "$TCP_PID" 2>/dev/null || true
fi

echo "Manual pair run complete. Logs: $TEST_DIR/"
