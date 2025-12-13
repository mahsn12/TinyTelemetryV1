#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(pwd)"
# default test dir inside project
TEST_DIR="$PROJECT_DIR/tests/loss5"
if [[ "$PROJECT_DIR" == /mnt/* ]]; then
    FALLBACK_BASE="/tmp/$(basename "$PROJECT_DIR")"
    TEST_DIR="$FALLBACK_BASE/tests/loss5"
fi
mkdir -p "$TEST_DIR"

SERVER_CMD="python3 -u TinyTelemetryV1_Server.py"
CLIENT_CMD="python3 -u TinyTelemetryV1_Client.py"
DURATION=${DURATION:-70}
IF=${IF:-eth0}

has_cmd(){ command -v "$1" >/dev/null 2>&1; }

NETEM_APPLIED=0
SIMULATE_NETEM=0

if has_cmd tc; then
    echo "Applying netem: loss 5% on $IF"
    if tc qdisc add dev "$IF" root netem loss 5% 2>/dev/null; then
        NETEM_APPLIED=1
    else
        echo "tc failed — falling back to simulation."
        SIMULATE_NETEM=1
    fi
else
    echo "tc not found — using simulation."
    SIMULATE_NETEM=1
fi

echo "Starting server..."
# capture server logs
( cd "$PROJECT_DIR" && env RUN_DURATION="$DURATION" PACKETS_CSV="$TEST_DIR/packets.csv" $SERVER_CMD 2>&1 | tee "$TEST_DIR/server.log" ) &
SERVER_PID=$!

SERVER_PORT=8888
echo "Waiting for server..."
for i in {1..50}; do
    if netstat -anu 2>/dev/null | grep -q ":$SERVER_PORT "; then break; fi
    sleep 0.2
done

echo "Starting client..."
if [ "$SIMULATE_NETEM" -eq 1 ]; then
    ( cd "$PROJECT_DIR" && env RUN_DURATION="$DURATION" SIMULATE_NETEM=1 SIMULATE_LOSS=0.05 $CLIENT_CMD 2>&1 | tee "$TEST_DIR/client.log" ) &
else
    ( cd "$PROJECT_DIR" && env RUN_DURATION="$DURATION" SIMULATE_NETEM=0 $CLIENT_CMD 2>&1 | tee "$TEST_DIR/client.log" ) &
fi
CLIENT_PID=$!

echo "Running for $DURATION seconds..."
sleep "$DURATION"

echo "Waiting for processes to exit (grace)..."
GRACE=6
for _ in $(seq 1 $GRACE); do
    if ! kill -0 "$SERVER_PID" 2>/dev/null && ! kill -0 "$CLIENT_PID" 2>/dev/null; then
        break
    fi
    sleep 1
done

if kill -0 "$CLIENT_PID" 2>/dev/null; then
    kill -15 "$CLIENT_PID" 2>/dev/null || true
fi
if kill -0 "$SERVER_PID" 2>/dev/null; then
    kill -15 "$SERVER_PID" 2>/dev/null || true
fi

if [ "$NETEM_APPLIED" -eq 1 ]; then
    echo "Removing netem..."
    tc qdisc del dev "$IF" root 2>/dev/null || true
fi

echo "Loss5 test complete. Logs: $TEST_DIR/"
# Attempt to copy logs back into project tests folder if possible
DEST_DIR="$PROJECT_DIR/tests/loss5"
mkdir -p "$DEST_DIR" 2>/dev/null || true
if cp "$TEST_DIR/server.log" "$DEST_DIR/server.log" 2>/dev/null; then
    echo "Copied logs back to $DEST_DIR"
else
    if command -v sudo >/dev/null 2>&1; then
        sudo cp "$TEST_DIR/server.log" "$DEST_DIR/server.log" 2>/dev/null || true
    fi
fi
if cp "$TEST_DIR/client.log" "$DEST_DIR/client.log" 2>/dev/null; then
    :
else
    if command -v sudo >/dev/null 2>&1; then
        sudo cp "$TEST_DIR/client.log" "$DEST_DIR/client.log" 2>/dev/null || true
    fi
fi
# copy packets.csv back if present
if [ -f "$TEST_DIR/packets.csv" ]; then
    if cp "$TEST_DIR/packets.csv" "$DEST_DIR/packets.csv" 2>/dev/null; then
        echo "Copied packets.csv back to $DEST_DIR"
    else
        if command -v sudo >/dev/null 2>&1; then
            sudo cp "$TEST_DIR/packets.csv" "$DEST_DIR/packets.csv" 2>/dev/null || true
        fi
    fi
fi
