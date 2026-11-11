# GB10 validation and provenance

## What the hardware checks establish

The original-model port was run on an NVIDIA GB10 ARM64 Linux system using the NGC PyTorch 25.11 CUDA environment. The deployed video, speech, ASR and Electron runtime containers were ARM64. Legacy x86-only artifacts were used for preparation and comparison; they were not used as emulated production inference services.

The following checks used real models and media:

| Area | Check |
| --- | --- |
| Original video models | DINetV1, WeNet and face-model outputs compared with the original implementations on recorded and synthetic inputs. |
| Video geometry/compositing | 422 cases/combinations for pose-aware cropping, alignment, masks, paste-back and interface behavior. These are not 422 full videos. |
| Source enhancement | A 116-frame blurred source exercised the original FaceAttr/GFPGAN enhancement path. GFPGAN FP32 TensorRT output was compared with the original ONNX model. |
| Frame rate and resolution | A 1408×1408 source was rendered using 29.97 processing FPS; the encoded rate was 30000/1001. Validation accounts for this representation difference. |
| Missing faces | A 10-frame no-face input produced valid output while preserving the source frames. |
| Long video | 125 seconds / 3,125 frames at 25 FPS; decoded source cache never exceeded eight frames. Peak process RSS was 2,619,644 KiB. The approximately 639-second run had other concurrent test workloads. |
| Optional mask | The XSeg blending path produced a 10-frame sample; the default remains the original landmark mask. |
| Speech | Real Fish 1.5 synthesis with deterministic seeds, normalization modes, multiple references, WAV/MP3/PCM and streaming. A disconnected stream released the model for a subsequent request. |
| Reference audio | Original RNNoise output comparisons and original FunASR recognition, followed by Fish synthesis, including the two-reference `|||` protocol. |
| ASR build | The original C++ runtime was rebuilt natively. The original Paraformer weights were exported to standard TorchScript and numerically checked, replacing the architecture-specific BladeDISC artifact. |
| GUI | Native file import, reference preprocessing, audition, text/audio generation, playback, export, search and deletion in the ARM64 packaged Electron application. |
| Deployed API | Original reference preprocessing → Fish → DINet produced a 4.04-second H.264/AAC video. Downloaded bytes matched the stored result; the whole file decoded successfully. |

These checks describe the port before its source files were reorganized for this contribution. The PR reports the additional tests/builds performed on the exact contributed layout separately. They should not be read as a fresh-machine rebuild of every download recipe, or a test of every input, language and sampling configuration.

## Automated checks

The desktop tests run without installing native dependencies:

```sh
npm test
```

Each backend module documents its unit-test dependencies and command. Protocol, queue and download tests do not require model downloads. GPU/model comparisons require separately prepared assets and are opt-in; CI does not pretend to run GB10 inference on a CPU runner.

## Limits and intentional differences

- The configured audio input limit is 1,800 seconds. A complete 30-minute render and sustained multi-user load have not been validated.
- Default playback follows the original ping-pong sequence, including repeated endpoint frames. Source FPS is rounded to two decimals before processing, matching the original helper.
- Failed face/pose detection preserves an unmodified source frame. This avoids the original fallback's mutable-array aliasing behavior.
- Completed API results remain queryable and jobs are persisted. A restart marks interrupted rendering as failed instead of trying to continue a partial output.
- The original ASR/ITN models can misrecognize numbers, repeat dates or format money incorrectly. Model retention does not imply error-free transcription.
- HTTP→HTTPS reference downloads and mixed local/URL references were tested with a controlled TLS server. Direct public HTTPS downloads also passed, but a full public-reference synthesis request encountered a CDN TLS timeout and is not counted as a passed end-to-end Internet test.
- This is the repository's offline video workflow. It does not add the separate commercial real-time interaction product or train a new avatar network.

## Source and model provenance

The repository's existing DUIX.COM Community License continues to apply to Duix-derived code. Geometry and preprocessing adapters restore behavior of the original distributed implementation; they are not presented as entirely independent model designs. Asset manifests identify original artifacts by source and digest.

Fish, FunASR, RNNoise, TorchAudio and their dependencies retain their respective licenses. The voice preparation recipe downloads the original image's text-normalization assets and applies a compatibility patch; those dictionaries and model files are not vendored into this PR. The TorchAudio-derived frontend includes its attribution/license next to the ported functions.

No model weights, vendor runtime binaries, recordings, production database contents or machine-specific access configuration are included. Prepared assets and generated data are ignored by Git. Keep upstream notices with any locally obtained artifacts.
