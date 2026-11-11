#!/bin/bash
set -eu
export DUIX_ASR_OFFLINE=1
export NVIDIA_TF32_OVERRIDE=0
export LD_LIBRARY_PATH=/opt/duix-funasr/lib:/usr/local/lib/python3.12/dist-packages/torch/lib:${LD_LIBRARY_PATH:-}
model_root=${ASR_MODELS_ROOT:-/models/voice/asr/original}
paraformer_dir=${ASR_PARAFORMER_DIR:-/models/voice/asr/paraformer}
exec /opt/duix-funasr/bin/funasr-wss-server \
 --download-model-dir "$model_root" \
 --model-dir "$paraformer_dir" \
 --vad-dir "$model_root/damo/speech_fsmn_vad_zh-cn-16k-common-onnx" \
 --punc-dir "$model_root/damo/punc_ct-transformer_cn-en-common-vocab471067-large-onnx" \
 --lm-dir "$model_root/damo/speech_ngram_lm_zh-cn-ai-wesp-fst" \
 --itn-dir "$model_root/thuduj12/fst_itn_zh" \
 --hotword /opt/duix-funasr/hotwords.txt \
 --decoder-thread-num "${ASR_DECODER_THREADS:-20}" \
 --model-thread-num "${ASR_MODEL_THREADS:-1}" --io-thread-num "${ASR_IO_THREADS:-2}" \
 --listen-ip 0.0.0.0 --port "${ASR_PORT:-10095}" --certfile '' --keyfile '' \
 --bladedisc false --batch-size "${ASR_BATCH_SIZE:-20}" --gpu
