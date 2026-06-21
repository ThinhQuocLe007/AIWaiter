#!/usr/bin/env bash
# Benchmark embedding models back-to-back.
#
# For each model in the list: set EMBEDDING_MODEL, rebuild the FAISS index +
# centroids, then run the retrieval and router evals. Results go to
# evals/results/bench_embedding/<sanitized-model-name>.log
#
# All models run on CPU by default (EMBEDDING_DEVICE=cpu) so the numbers reflect
# Jetson CPU latency; export EMBEDDING_DEVICE=cuda before running to override.
# Override the model list by passing models as args:
#   scripts/bench_embedding.sh intfloat/multilingual-e5-small bkai-foundation-models/vietnamese-bi-encoder
set -euo pipefail

cd "$(dirname "$0")/.."

# Force CPU embeddings unless the caller already set it.
export EMBEDDING_DEVICE="${EMBEDDING_DEVICE:-cpu}"

MODELS=("$@")
if [ ${#MODELS[@]} -eq 0 ]; then
  MODELS=(
    "AITeamVN/Vietnamese_Embedding"
    "bkai-foundation-models/vietnamese-bi-encoder"
    "dangvantuan/vietnamese-embedding"
    "keepitreal/vietnamese-sbert"
    "intfloat/multilingual-e5-small"
    "intfloat/multilingual-e5-base"
    "Alibaba-NLP/gte-multilingual-base"
  )
fi

OUT_DIR="evals/results/bench_embedding"
mkdir -p "$OUT_DIR"

for MODEL in "${MODELS[@]}"; do
  SAFE=$(echo "$MODEL" | tr '/:' '__')
  LOG="$OUT_DIR/$SAFE.log"
  echo "============================================================"
  echo " Embedding model: $MODEL"
  echo " Log: $LOG"
  echo "============================================================"

  {
    echo "### MODEL: $MODEL"
    echo "### $(date)"
    echo
    echo "--- rebuild (FAISS + centroids) ---"
    EMBEDDING_MODEL="$MODEL" uv run python scripts/setup.py --embeddings-only
    echo
    echo "--- eval_retrieval ---"
    EMBEDDING_MODEL="$MODEL" uv run python evals/scripts/eval_retrieval.py
    echo
    echo "--- eval_router ---"
    EMBEDDING_MODEL="$MODEL" uv run python evals/scripts/eval_router.py
  } 2>&1 | tee "$LOG"

  echo
done

echo "Done. Per-model logs in $OUT_DIR/"
