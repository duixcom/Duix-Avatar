# Original video models on GB10

This module runs the original DINetV1, WeNet, SCRFD/PFPLD, WHENet, GFPGAN and
FaceAttr models on Linux ARM64 / NVIDIA GB10. Landmark mouth blending is the
default; `--blend xseg` enables the original optional XSeg branch. Model weights,
TensorRT engines, extracted vendor code and reference media are not in Git.

The Python host interfaces and scheduling are portable. The original network
graphs are exported with their original weights; no replacement lip-sync model
is used. Original model and dependency licenses continue to apply. The export
tools load the pinned network modules only, without importing the original
service or modifying any license mechanism.

## Layout and service interface

The image contains code at `/opt/duix/video`. Mount a prepared model directory
at `/models/video`, and writable jobs/media at `/data`:

```text
assets/video/
  runtime-model-manifest.json       # generated after original graph comparison
  full-model-manifest.json          # original ONNX hashes + locally verified engine
  export-fp32/                      # original DINet graph, metadata and generated test vectors
  export-wenet/                     # original WeNet graph and generated test vectors
  face-models/                      # SCRFD, PFPLD and original silence feature
  models/                          # original enhancement/pose ONNX and local GFPGAN engine
```

`full_service.py --root /models/video --full-root /models/video --data-root /data`
serves `POST /easy/submit`, `GET /easy/query`, `GET /results/<job>.mp4` and
`GET /health` on port 8383. The top-level GB10 Compose file provides these mounts.
The health endpoint reports model readiness, worker liveness and persistence
errors; it returns a failing status if the worker cannot serve jobs.

The complete runtime is in this directory. `runner.py` contains media probing
and subprocess helpers, and `server.py` contains the shared HTTP handler.
`original_runner.py` is only the shared model loader; `full_runner.py` supplies
the current pose-aware preprocessing, source enhancement and video composition.

## Prepare original assets

Run the following commands from the repository root. Use a new preparation
directory; do not replace files under a running service's read-only model mount.
The video source/model layer is approximately 1.23 GB compressed, plus extracted
files and exported models. Docker Hub access is needed for the fixed blob.

```bash
mkdir -p deploy/gb10/assets/video
python deploy/gb10/scripts/prepare_video_models.py download \
  --cache-dir deploy/gb10/cache/registry \
  --code-root deploy/gb10/vendor/video-code
```

`model-sources.json` pins the original layer and raw model hashes. The downloader
checks the entire compressed blob before extraction, extracts regular `code/`
files only, rejects path traversal, and never runs the image. A failed transfer
leaves a `.part` file; retrying downloads it again. A complete verified blob is
reused from the cache. An existing nonempty code directory is not overwritten.

DINet/WeNet export requires **x86_64 CPython 3.9**, because the original graph
implementations are x86 Cython extensions and Python 3.9 bytecode. Production
inference is native ARM64 CUDA. On an x86 Linux export machine:

```bash
docker build --platform linux/amd64 -f deploy/gb10/video/Dockerfile.export \
  -t duix-avatar-video-export:local deploy/gb10/video
docker run --rm --platform linux/amd64 --user "$(id -u):$(id -g)" \
  -e HOME=/tmp -e MPLCONFIGDIR=/tmp/matplotlib -e NUMBA_CACHE_DIR=/tmp/numba \
  -v "$PWD/deploy/gb10/vendor/video-code:/source:ro" \
  -v "$PWD/deploy/gb10/assets/video:/models/video" \
  duix-avatar-video-export:local --code-root /source --model-root /models/video
```

Copy the prepared `assets/video` directory to the GB10 host if export ran on
another machine. No extracted x86 extensions are needed by the production image.
The export checks original checkpoint identity, strict parameter coverage,
extension/bytecode equivalence for DINet, and original eager versus saved graph
outputs. WeNet's traced integer shape mask is made dynamic; tensor math and
weights are preserved. CPU device constants follow input tensors on CUDA.

`runtime-model-manifest.json` is generated only after those comparisons pass.
Serialized graph hashes can differ between export environments; their locally
validated hashes are recorded instead of copying a machine-specific export hash.
Raw ONNX/checkpoint identities remain fixed. Keep the generated comparison
vectors with the model preparation directory to run the CUDA checks below.

The same preparation can be driven directly with the pinned Python dependencies
in `requirements-export.txt`, Torch/TorchAudio 2.8.0 CPU, and `export_models.py`.
`prepare_video_models.py install` installs verified raw ONNX files;
`prepare_video_models.py finalize` checks completed export reports and records
the current local graph hashes. Neither accepts a failed comparison as success.

## Native image and CUDA checks

On GB10 with NVIDIA Container Toolkit:

```bash
docker compose -f deploy/gb10/docker-compose.yml build video
docker run --rm --gpus all --user "$(id -u):$(id -g)" \
  -v "$PWD/deploy/gb10/assets/video:/models/video" \
  duix-avatar-gb10-video:local python verify_dinet_cuda.py \
  --root /models/video/export-fp32 --report /models/video/dinet-cuda-validation.json
docker run --rm --gpus all --user "$(id -u):$(id -g)" \
  -v "$PWD/deploy/gb10/assets/video:/models/video" \
  duix-avatar-gb10-video:local python verify_wenet_cuda.py \
  --model /models/video/export-wenet/original-wenet.ts \
  --verification /models/video/export-wenet/original-wenet-verification.pt \
  --output /models/video/wenet-cuda-validation.json
docker run --rm --gpus all --user "$(id -u):$(id -g)" --shm-size 2g \
  -v "$PWD/deploy/gb10/assets/video:/models/video" \
  duix-avatar-gb10-video:local python build_gfpgan.py --model-root /models/video
```

GFPGAN builds from the pinned original ONNX with FP32 and TF32 disabled. Before
installing an engine, the tool compares it against original ONNX CPU inference
on three deterministic synthetic images. No private photos, videos or oracle
vector files are required. Only a passing engine is installed and added to the
local manifest. TensorRT engine hashes may change with hardware/build timing;
the new hash is accepted only after the declared numerical comparison passes.

To verify an already built engine without rebuilding it, run
`gfpgan_validation.py --onnx <original.onnx> --engine <local.engine> --report <report.json>`
inside the native video image. The tolerance is 2e-4 absolute / 1e-4 relative,
with finite output and at most one uint8 output level of difference.

The runtime image starts from the NGC PyTorch 25.11 ARM64 CUDA environment and
does not install a replacement PyTorch wheel. Model preparation is a separate
step; building the image alone does not install model assets. See the top-level
GB10 documentation for starting the complete video/TTS/ASR stack.

## Tests and behavior

CPU-only tests create their own small synthetic videos and temporary job files:

```bash
PYTHONPATH=deploy/gb10/video python -m unittest discover -s deploy/gb10/video/tests -v
```

Three optional original API comparisons require the downloaded source and are
skipped by default. Set `DUIX_ORIGINAL_CODE_ROOT` to the extracted code directory
to enable them; the original API file is checksum-checked before its isolated
request functions are evaluated. No original worker or licensing code runs.

The implementation retains source resolution and the original two-decimal
processing frame rate. Default `pn=1` repeats both endpoints while playing the
reference forward/backward; `pn=0` loops forward. No-face/invalid-pose frames
keep their source pixels, fixing the original placeholder-crop aliasing bug.
Odd dimensions are made even for encoding. The original H264 CRF15/AAC output
policy and default landmark blend are retained.

Input audio may be up to 1800 seconds; the largest completed end-to-end
acceptance before this contribution was 125 seconds, not 30 minutes. Source
decoding uses a bounded frame cache; jobs run serially and survive query/restart
semantics with explicit failed-job recovery. A process restart marks unfinished
jobs failed rather than claiming to resume an incomplete render. Floating-point
and codec behavior can vary by backend; this is not a promise of pixel-identical
output for arbitrary input media.
