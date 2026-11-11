Fetched components are kept in ignored assets, not redistributed in this Git
tree. `sources.json` records immutable source revisions and SHA-256 checksums.

| Component | Upstream/source | License notice retained |
| --- | --- | --- |
| Fish Speech | `fishaudio/fish-speech`, commit `7902e408c85b37193ce3f3c2361ca3c76be0d533` | Upstream `LICENSE` in prepared source |
| Duix text normalizer and Fish checkpoint | Original `guiji2025/fish-speech-ziming` layer 37 | Original artifact notices and Duix terms; no replacement license asserted |
| FunASR | Original `guiji2025/fun-asr` source layers; architecture revision `df24be289221a37b55f9853d2083cf5a0a5382dc` | FunASR `LICENSE` and runtime third-party notices |
| ONNX Runtime | Microsoft v1.20.1 AArch64 archive | `LICENSE`, `ThirdPartyNotices.txt` |
| RNNoise core/model | `xiph/rnnoise`, commit `7f449bf8bd3b933891d12c30112268c4090e4d59` | `COPYING` |
| RNNoise audio CLI | `cpuimage/rnnoise`, commit `21af48b754fb39b4171da69e71ef5b3f3806a842` | `COPYING-cpuimage`, embedded dr_wav/dr_mp3 notices |
| Mel filter bank helper | PyTorch Audio v2.10.0 | `duix_fish/TORCHAUDIO_LICENSE`, source attribution in module |
| NLTK words corpus | Official `nltk/nltk_data` words archive | Corpus `README` retained |

The preparation script fetches the original model assets; this contribution
does not grant additional rights to the weights or third-party software.
