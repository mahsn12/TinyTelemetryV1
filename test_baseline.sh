#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(pwd)"
TEST_DIR="$PROJECT_DIR/tests/baseline"
mkdir -p "$TEST_DIR"

SERVER_CMD="python3 -u TinyTelemetryV1_Server.py"
CLIENT_CMD="python3 -u TinyTelemetryV1_Client.py"
DURATION=${DURATION:-70}

echo "Starting server..."
# pass RUN_DURATION to server so server stops itself
( cd "$PROJECT_DIR" && env RUN_DURATION="$DURATION" $SERVER_CMD 2>&1 | tee "$TEST_DIR/server.log" ) &
SERVER_PID=$!

SERVER_PORT=8888
echo "Waiting for server to bind UDP $SERVER_PORT..."
for i in {1..50}; do
    if netstat -anu 2>/dev/null | grep -q ":$SERVER_PORT "; then
        echo "Server is listening on UDP $SERVER_PORT"
        break
    fi
    sleep 0.2
done

echo "Starting client..."
( cd "$PROJECT_DIR" && env RUN_DURATION="$DURATION" SIMULATE_NETEM=0 $CLIENT_CMD 2>&1 | tee "$TEST_DIR/client.log" ) &
CLIENT_PID=$!

echo "Running for $DURATION seconds..."
sleep "$DURATION"

echo "Waiting for processes to exit (grace)..."
# give them a short grace period to exit cleanly
GRACE=6
for _ in $(seq 1 $GRACE); do
    if ! kill -0 "$SERVER_PID" 2>/dev/null && ! kill -0 "$CLIENT_PID" 2>/dev/null; then
        break
    fi
    sleep 1
done

# Fallback: if still alive, send SIGTERM (gentle)
if kill -0 "$CLIENT_PID" 2>/dev/null; then
    kill -15 "$CLIENT_PID" 2>/dev/null || true
fi
if kill -0 "$SERVER_PID" 2>/dev/null; then
    kill -15 "$SERVER_PID" 2>/dev/null || true
fi

echo "Baseline test complete. Logs: $TEST_DIR/"
