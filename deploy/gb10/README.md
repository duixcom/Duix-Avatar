# NVIDIA GB10 / Linux ARM64

This optional deployment runs the original Duix offline avatar workflow on an ARM64 Linux host with an NVIDIA GB10 GPU. It includes an ARM64 Electron client, a native video service, Fish Speech, and the original FunASR pipeline. Existing Windows and x86 deployment files are unchanged.

The model families remain DINetV1/WeNet, SCRFD/PFPLD/WHENet, GFPGAN/FaceAttr, Fish Speech 1.5, RNNoise, and Paraformer/FSMN-VAD/punctuation/WFST/ITN. This is an architecture port; it does not substitute a different lip-sync, TTS, or ASR model.

## Requirements

- Linux ARM64, an NVIDIA GB10 GPU, and a driver compatible with the CUDA runtime in the pinned NGC PyTorch image.
- Docker Engine, Docker Compose v2, and NVIDIA Container Toolkit already configured. Check GPU access before building; these scripts do not modify host drivers or the Docker daemon.
- Python 3.10+ for asset preparation; Node.js 18+ and native build tools for the desktop client.
- Sufficient space for the upstream container layers, model assets, image builds, and generated media. The original deployment documentation recommends more than 100 GB; keeping download caches and build intermediates increases usage.

Model preparation uses separately downloaded upstream assets. Review the repository's [license](../../LICENSE) and the respective model/code licenses before downloading. Weights, compiled engines, vendor binaries, and media are not distributed in this contribution. Once assets are prepared, local-reference synthesis does not require an Internet connection.

## Components and preparation

- [Video service and original-model export](video/README.md)
- [Speech, reference preprocessing, and original ASR](voice/README.md)
- [ARM64 desktop client](../../docs/gb10-client.md)

Follow both backend preparation guides before starting Compose. Their outputs live under `assets/`, which is ignored by Git. Keep the layout documented by each module: runtime model paths and checksums are validated at startup. Initial export of legacy Python extensions may require a separate x86 preparation environment; the deployed services themselves run natively on ARM64.

## Start the services

From this directory:

```sh
cp .env.example .env
# Set DUIX_UID/DUIX_GID to your local user and choose absolute data/cache paths if needed.
mkdir -p data/face2face/temp data/voice/data/origin_audio cache/video cache/tts

docker compose build
docker compose up -d --wait
```

If the default Ubuntu Ports server is slow in your network, set `DUIX_APT_MIRROR` to a trusted Ubuntu Ports mirror before building. This changes the image build only; it does not edit host package sources or drivers. Leave it empty to use the official source.

The video and TTS ports bind to loopback by default. The ASR websocket is internal to the Compose network. Run the Electron client in a desktop session.

Use one data root for the client and both backends. From the repository root, set `DUIX_DATA_ROOT` to the absolute path of `deploy/gb10/data` (or the data path selected in `.env`), then follow the client guide. If the HTTP ports were changed, set `DUIX_F2F_URL=http://127.0.0.1:<video-port>/easy` and `DUIX_TTS_URL=http://127.0.0.1:<tts-port>` for the client.

```sh
export DUIX_DATA_ROOT="$PWD/deploy/gb10/data"
npm ci
npm run build:linux:arm64
```

Launch the generated Linux application in a desktop session. Import a source video, create its reference voice, audition text, and generate a video from either text or uploaded audio. The backend API works with files under the shared data root; URL reference audio in the speech service has separate network/size/time limits described in its guide.

## Validation and limitations

See [validation notes](VALIDATION.md) for tested behavior and the difference between unit tests, model comparisons, and hardware checks. The original-model deployment was exercised on GB10 with source import, RNNoise/ASR preprocessing, audition, text/audio video generation, preview, export, and queue recovery. The long-video hardware run produced 125 seconds / 3,125 frames; the configured 30-minute input limit has not been validated by a full 30-minute render.

The original no-face fallback can accidentally reuse a mutated frame. This port preserves the source frame when face/pose detection fails. Original numerical date/money recognition and ITN quality limitations remain. Network reference downloads can fail when the remote server or CDN is unavailable. None of these tests establish pixel-for-pixel or word-for-word equivalence for every input.

## Operations

```sh
docker compose ps
docker compose logs --tail=100 video tts asr
docker compose stop
```

All services use restart policies. Wait for queued jobs to finish before stopping or upgrading. An interrupted render is marked failed after restart; it is not resumed mid-frame. Completed job records and media remain on disk. Back up the data directory, desktop profile/SQLite database, model manifests, and your current configuration before an upgrade. Retain previous images/configuration for application rollback; restoring an older data backup can discard newer work.
