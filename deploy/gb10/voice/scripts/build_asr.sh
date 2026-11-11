set -eu
cd /voice/FunASR
python - <<'PY'
from pathlib import Path
import torch
root=Path('/voice/FunASR/runtime')
for name in ['websocket/CMakeLists.txt','onnxruntime/CMakeLists.txt']:
 p=root/name;s=p.read_text().replace('set(CMAKE_CXX_STANDARD 14','set(CMAKE_CXX_STANDARD 17')
 s=s.replace('set(TORCH_DIR "/usr/local/lib/python3.8/dist-packages/torch")', 'set(TORCH_DIR "'+str(Path(torch.__file__).parent)+'")')
 s=s.replace('-D_GLIBCXX_USE_CXX11_ABI=0','-D_GLIBCXX_USE_CXX11_ABI='+str(int(torch._C._GLIBCXX_USE_CXX11_ABI)))
 p.write_text(s)
p=root/'onnxruntime/src/CMakeLists.txt';p.write_text(p.read_text().replace('torch_blade ral_base_context',''))
# Build only the offline server, no microphone/portaudio clients are used by Duix.
p=root/'websocket/bin/CMakeLists.txt';s=p.read_text();s='\n'.join(x for x in s.splitlines() if not any(t in x for t in ['add_executable(funasr-wss-client','target_link_libraries(funasr-wss-client','add_executable(funasr-wss-server-2pass','target_link_options(funasr-wss-server-2pass','target_link_libraries(funasr-wss-server-2pass']))+'\n';p.write_text(s)
PY
cmake -S runtime/websocket -B /voice/asr-build -DCMAKE_BUILD_TYPE=Release -DGPU=ON -DENABLE_PORTAUDIO=OFF -DONNXRUNTIME_DIR=/voice/deps/onnxruntime-linux-aarch64-1.20.1 -DFFMPEG_DIR=/usr -DCMAKE_POLICY_VERSION_MINIMUM=3.5
cmake --build /voice/asr-build --target funasr-wss-server -j 6
