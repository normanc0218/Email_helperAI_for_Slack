#!/bin/bash
# Run ADK evals for email_agent (fully isolated — no real Firebase/Gmail).
# Usage (from project root):
#   bash agent_service/email_agent/evals/run_evals.sh
#   bash agent_service/email_agent/evals/run_evals.sh common safety

AGENT_DIR="agent_service/email_agent"
CONFIG_DIR="$AGENT_DIR/evals"
EMAIL_PROVIDER="${EMAIL_PROVIDER:-fake}"
EVAL_MODE="${EVAL_MODE:-true}"

CATEGORIES=(intent_classification common ambiguous edge memory safety)
[ $# -gt 0 ] && CATEGORIES=("$@")

echo "EMAIL_PROVIDER=$EMAIL_PROVIDER  EVAL_MODE=$EVAL_MODE  categories: ${CATEGORIES[*]}"
echo ""

PASS=0; FAIL=0

for cat in "${CATEGORIES[@]}"; do
  evalset="$AGENT_DIR/$cat.evalset.json"
  config="$CONFIG_DIR/$cat.evalconfig.json"

  [ -f "$evalset" ] || { echo "[$cat] SKIP — evalset not found"; continue; }

  printf "%-28s " "[$cat]"
  cmd="EMAIL_PROVIDER=$EMAIL_PROVIDER EVAL_MODE=$EVAL_MODE adk eval $AGENT_DIR $evalset"
  [ -f "$config" ] && cmd="$cmd --config_file_path $config"

  errors=$(eval "$cmd" 2>&1 | grep -c "ERROR.*Inference failed" || true)
  if [ "$errors" -gt 0 ]; then
    echo "FAIL ($errors errors)"; FAIL=$((FAIL+1))
  else
    echo "PASS"; PASS=$((PASS+1))
  fi
done

echo ""
echo "Result: $PASS passed, $FAIL failed"
[ $FAIL -eq 0 ] && exit 0 || exit 1
