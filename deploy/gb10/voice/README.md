This directory contains the ARM64 voice adapter and reproducible build recipes.
Run commands below from `deploy/gb10`. Model/source downloads are written under
`assets/voice/`, which must remain excluded from Git.

```sh
python3 voice/prepare_assets.py
docker build -f voice/Dockerfile.tts -t duix-avatar-gb10-tts:local .
docker build -f voice/Dockerfile.asr --target exporter -t duix-gb10-asr-exporter .
docker run --rm -v "$PWD/assets/voice/models:/models/voice" duix-gb10-asr-exporter
docker build -f voice/Dockerfile.asr --target runtime -t duix-avatar-gb10-asr:local .
```

The optional build argument `APT_MIRROR` selects an Ubuntu Ports mirror; its
default is empty, preserving the base image's official repository. For example,
`--build-arg APT_MIRROR=https://mirrors.ustc.edu.cn/ubuntu-ports` can be used where
the official repository is slow. It changes only the container build.

Preparation requires Python 3.10+, `patch`, network access and several GB of
free disk space. `--component fish|asr|rnnoise` selects a component;
`--sources-only` skips separate runtime model directories. Every download is
size/SHA-256 checked against `sources.json`. Partial downloads resume where the
server supports ranges. Existing prepared directories are never silently
overwritten. When changing the recipe, move the affected directory aside first.
Downloads are cached separately and can be reused with `--cache`.

FunASR is reconstructed from the original public image's layers 29, 30, 32 and
34 in that order, applying Docker whiteouts. Only its Python exporter and C++
WebSocket/ONNX runtime source trees are selected; old compiled binaries are
discarded. Original ASR weights come from layer 36. The CPU exporter uses a
separate Torch 2.8 environment and checks the original Paraformer checkpoint SHA
before loading it, verifies every state tensor, and tests four input shapes.
It writes `model.torchscript`, `config.yaml`, `tokens.json`, `am.mvn` and an
export report into `assets/voice/models/asr/paraformer/`.

Fish source is pinned to its upstream commit. The original image layer 37
supplies Fish Speech 1.5 weights and `tools/text_norm`, including the original
XGBoost model. Small patches make imports, audio I/O and text normalization
portable. The NLTK word list is prepared ahead of time: serving needs no startup
download. The NGC GPU Torch build is retained unchanged.

RNNoise uses pinned Xiph neural weights and core source plus the pinned
cpuimage audio CLI. The CLI patch selects the original float-WAV output and
model-constructor API. Both source licenses are retained in the image. No model
arrays or compiled binaries are checked into this contribution.

Runtime paths and interfaces:

| Service | Endpoint | Model mount | Shared media |
| --- | --- | --- | --- |
| Fish TTS | HTTP 18180 `/v1/health`, `/v1/invoke`, `/v1/preprocess_and_tran` | `/models/voice/fish-speech-1.5` | `/data` |
| Original ASR | WebSocket 10095 | `/models/voice/asr/original`, `/models/voice/asr/paraformer` | Audio sent over WebSocket |

`Dockerfile.tts` has `ENTRYPOINT ["python", "-m", "duix_fish"]`; container
arguments should contain only options. The service supports WAV/MP3/PCM,
streaming WAV, seed, both normalization options and `|||` multiple references.
Reference preprocessing uses the original RNNoise, segmentation and complete
Paraformer/VAD/punctuation/WFST/ITN path. Uploads are preserved.

HTTP/HTTPS reference URLs have a 50 MiB default limit, 30-second deadline and
three-redirect limit. Each hop checks DNS addresses and connects to a checked
address while preserving HTTPS hostname/certificate verification. Private,
loopback and link-local targets are refused by default. An administrator can
explicitly allow a trusted server using repeated `--reference-url-allow-network`
options or comma-separated `DUIX_REFERENCE_URL_ALLOW_NETWORKS`. Set
`DUIX_REFERENCE_URL_MAX_BYTES` to change the URL size limit. This limit does not
truncate local uploaded recordings. Credential-bearing URLs are rejected;
URL queries and credentials are not logged. Environment HTTP proxies are not
used. A failed TLS/body transfer is reported as a failure; no success audio is
fabricated. DNS proxy deployments must opt in to only their trusted proxy CIDR.

Tests use generated audio and an isolated local HTTP server:

```sh
python -m pip install -r voice/requirements-test.txt
PYTHONPATH=voice python -m unittest discover -s voice/tests -v
```

These protocol tests do not claim model quality. Native model/algorithm parity
and actual Fish/ASR generation were separately exercised during the GB10 port;
see the deployment validation notes. The original models can still repeat
words or normalize dates/currency unexpectedly. Source licenses and model-use
terms remain those of their respective upstreams; downloading or converting
an artifact does not change its license.
