# Linux ARM64 client and configurable local services

The Electron client can be built natively on Linux ARM64, including NVIDIA GB10
systems. This changes the client architecture and media-tool paths. The inference
services must also support the target hardware; an ARM64 client does not make an
x86-only backend image compatible with GB10.

## Build on Linux ARM64

Install Node.js and npm, the native build tools required by `better-sqlite3`, and
system `ffmpeg`/`ffprobe`. Node.js 22 was used for the client checks. In a native
ARM64 checkout, run:

```sh
npm ci
npm test
npm run build:linux:arm64
```

The ARM64 command rebuilds native Electron dependencies before packaging and
uses `electron-builder.arm64.yml`. Its outputs include
`dist/linux-arm64-unpacked` and an AppImage whose filename includes `arm64`.
Build on ARM64; this command does not install a cross-compilation toolchain on
an x64 host. Use separate checkouts when building for different architectures
so their native `node_modules` do not overwrite each other.

The existing `build:win` and `build:linux` commands and default packaging
configuration are unchanged. Their artifact names remain unchanged.

## Runtime configuration

Set these optional environment variables before launching the client:

| Variable | Purpose | Default |
| --- | --- | --- |
| `DUIX_DATA_ROOT` | Shared media root | Windows: `D:\duix_avatar_data`; other platforms: `$HOME/duix_avatar_data` |
| `DUIX_F2F_URL` | Video API base, including `/easy` | `http://127.0.0.1:8383/easy` |
| `DUIX_TTS_URL` | Speech API base | `http://127.0.0.1:18180` |
| `DUIX_FFMPEG_PATH` | Explicit FFmpeg executable | Linux ARM64: `/usr/bin/ffmpeg`; Windows/Linux x64: original bundled executable |
| `DUIX_FFPROBE_PATH` | Explicit FFprobe executable | Linux ARM64: `/usr/bin/ffprobe`; Windows/Linux x64: original bundled executable |

For example, with both services running locally and sharing `/srv/duix/data`:

```sh
DUIX_DATA_ROOT=/srv/duix/data \
  DUIX_F2F_URL=http://127.0.0.1:8383/easy \
  DUIX_TTS_URL=http://127.0.0.1:18180 \
  npm start
```

The client writes video inputs/results under `face2face/temp` and voice inputs
under `voice/data` beneath this root. Point the backend mounts at those same
directories. Changing an API URL alone does not transfer local media to another
machine. The application database remains in Electron's existing user-data
directory; `DUIX_DATA_ROOT` changes media paths only.

Production defaults retain the existing Windows data layout and Windows/Linux
x64 media executable layout. Development now also uses localhost unless an API
URL is explicitly set; it no longer depends on a hardcoded developer LAN
address or substitutes `test.wav`/`test.mp4` for the selected media.

## Queue and upload behavior

- A slow speech request stays pending until its video job code is available.
- Temporary status-query errors are retried. Missing jobs (`10003` or `10004`)
  and unreadable result files fail explicitly, allowing subsequent queued work
  to continue.
- After a client restart, a submitted job retains its code and is polled again.
  An interrupted submission without a code is marked failed so it can be retried.
  This does not resume a rendering that the backend itself has lost.
- The existing 30-minute audio upload limit is unchanged. Its translated error
  message now works in the Vue component's script as well as its template.

`npm test` covers platform paths, environment overrides and queue recovery
without requiring models, a GPU, or running inference services. A production
build and native ARM64 packaging check remain separate from those unit tests.
