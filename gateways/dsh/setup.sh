#!/usr/bin/env bash
# Prepare two DeepSeek Harness homes for the `dsh` system row (EXPERIMENTAL).
#
#   pip install "deepseek-harness-sdk==0.1.2rc1"      # the Python SDK bundles dsh
#   bash gateways/dsh/setup.sh                        # needs Node 22+ on PATH for the plugin install
#   python -m failoverbench wall --profile full -v
#   python -m failoverbench run --system systems/dsh.yaml --profile full
#
# Each home gets settings.yaml with the wall as an OpenAI-compatible provider named
# `fake`, every scenario model, the baseline retry policy (2 retries, 30 s stream
# idle timeout) and a dsh-llm-fallbacks chain: fb-ok for home-default,
# fb-ok-noprefill for home-noprefill (scenario S14).
set -euo pipefail
cd "$(dirname "$0")"
export FAKE_API_KEY="${FAKE_API_KEY:-failoverbench}"
DSH_VERSION="${DSH_VERSION:-0.1.2-rc.1}"
PLUGIN_VERSION="${PLUGIN_VERSION:-0.4.2}"

models=$(python3 - <<'EOF'
import yaml
cat = yaml.safe_load(open("../../scenarios/catalogue.yaml"))
ids = ["fb-ok", "fb-ok-noprefill"] + [s["model"] for s in cat["scenarios"]]
print("\n".join(f"        - id: {m}" for m in dict.fromkeys(ids)))
EOF
)

write_home () {
  local home="$1" chain_tail="$2"
  mkdir -p "$home" ../../gateways/dsh/workspace
  cat > "$home/settings.yaml" <<EOF
llm-pi-ai:
  providers:
    fake:
      apiKeyEnv: FAKE_API_KEY
      api: openai-completions
      baseURL: http://127.0.0.1:8401/v1
      streamIdleTimeoutMs: 30000
      retryPolicy: { mode: normal, maxRetries: 2 }
      models:
$models
fallbacks:
  enabled: true
  triggerCodes: [AUTH, QUOTA, RATE_LIMIT, SERVER, TIMEOUT, TRANSPORT, EMPTY_RESPONSE]
  rootChain: [fake/$chain_tail]
  cooldownMs: 30000
  recovery: half-open
  presets: none
  roleAutoMatch: false
EOF
  echo "wrote $home/settings.yaml (chain -> fake/$chain_tail)"
  # Initialise the sdk profile and install the fallback plugin into this home.
  DSH_HOME="$(cd "$home" && pwd)" npx --yes "@deepseek-ai/dsh@${DSH_VERSION}" --profile sdk --dump-default-config >/dev/null
  DSH_HOME="$(cd "$home" && pwd)" npx --yes "@deepseek-ai/dsh@${DSH_VERSION}" plugin --profile sdk add "dsh-llm-fallbacks@${PLUGIN_VERSION}"
  DSH_HOME="$(cd "$home" && pwd)" npx --yes "@deepseek-ai/dsh@${DSH_VERSION}" --profile sdk --dump-config | grep -q "llm-fallbacks" \
    && echo "plugin active in $home" || echo "WARNING: llm-fallbacks not found in $home config dump"
}

write_home home-default fb-ok
write_home home-noprefill fb-ok-noprefill
echo "done. Homes: gateways/dsh/home-default, gateways/dsh/home-noprefill"
