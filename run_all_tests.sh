#!/usr/bin/env bash
set -euo pipefail

DURATION=${DURATION:-80}
WAIT_BETWEEN=${WAIT_BETWEEN:-5}

echo "====================================="
echo " Running Baseline Test"
echo " Duration: ${DURATION} seconds"
echo "====================================="
DURATION="$DURATION" bash test_baseline.sh

echo ""
echo ">>> Waiting ${WAIT_BETWEEN} seconds before next test..."
sleep "${WAIT_BETWEEN}"
echo ""

echo "====================================="
echo " Running Loss 5% Test"
echo " Duration: ${DURATION} seconds"
echo "====================================="
DURATION="$DURATION" bash test_loss5.sh

echo ""
echo ">>> Waiting ${WAIT_BETWEEN} seconds before next test..."
sleep "${WAIT_BETWEEN}"
echo ""

echo "====================================="
echo " Running Delay + Jitter Test"
echo " Duration: ${DURATION} seconds"
echo "====================================="
DURATION="$DURATION" bash test_delay_jitter.sh

echo ""
echo "====================================="
echo " All tests completed!"
echo " Logs available in ./tests/"
echo "====================================="
