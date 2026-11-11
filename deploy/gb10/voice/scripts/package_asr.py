from pathlib import Path
import shutil,hashlib,json,subprocess
base=Path('/voice');out=base/'runtime-image';runtime=out/'runtime'
(runtime/'bin').mkdir(parents=True,exist_ok=True);(runtime/'lib').mkdir(exist_ok=True);(runtime/'licenses').mkdir(exist_ok=True)
shutil.copy2(base/'asr-build/bin/funasr-wss-server',runtime/'bin/funasr-wss-server')
for pattern in ['asr-build/src/libfunasr.so*','asr-build/openfst/src/lib/libfst.so*','asr-build/yaml-cpp/libyaml-cpp.so*','asr-build/glog/libglog.so*','asr-build/gflags/libgflags.so*','deps/onnxruntime-linux-aarch64-1.20.1/lib/libonnxruntime.so*','deps/onnxruntime-linux-aarch64-1.20.1/lib/libonnxruntime_providers_shared.so']:
 for p in base.glob(pattern):
  target=runtime/'lib'/p.name
  if target.exists() or target.is_symlink():target.unlink()
  if p.is_symlink():target.symlink_to(p.readlink())
  else:shutil.copy2(p,target)
for p in Path('/usr/lib/aarch64-linux-gnu').glob('libgflags.so*'):
 target=runtime/'lib'/p.name
 if target.exists() or target.is_symlink():continue
 if p.is_symlink():target.symlink_to(p.readlink())
 else:shutil.copy2(p,target)
shutil.copy2(base/'FunASR/runtime/websocket/hotwords.txt',runtime/'hotwords.txt')
for title,path in [('FunASR','FunASR/LICENSE'),('ONNXRuntime','deps/onnxruntime-linux-aarch64-1.20.1/LICENSE'),('ONNXRuntime-ThirdParty','deps/onnxruntime-linux-aarch64-1.20.1/ThirdPartyNotices.txt'),('OpenFST','FunASR/runtime/onnxruntime/third_party/openfst/COPYING'),('yaml-cpp','FunASR/runtime/onnxruntime/third_party/yaml-cpp/LICENSE'),('glog','FunASR/runtime/onnxruntime/third_party/glog/COPYING'),('gflags','FunASR/runtime/onnxruntime/third_party/gflags/COPYING.txt')]:
 p=base/path
 if p.exists():shutil.copy2(p,runtime/'licenses'/title)
shutil.copy2(base/'scripts/run_asr.sh',runtime/'run.sh');(runtime/'run.sh').chmod(0o755)
files=[]
for p in runtime.rglob('*'):
 if p.is_file() and not p.is_symlink():files.append({'path':str(p.relative_to(runtime)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size})
(out/'runtime-manifest.json').write_text(json.dumps(files,indent=2));print({'runtime_files':len(files),'bytes':sum(p['bytes'] for p in files)})
