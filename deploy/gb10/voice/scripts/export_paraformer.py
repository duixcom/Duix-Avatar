"""Export the official Paraformer checkpoint using its shipped FunASR architecture."""
import argparse,copy,json,os,time,hashlib,shutil
from pathlib import Path
import torch
from funasr import AutoModel
# FunASR suppresses optional import failures during registry discovery. Import
# this checkpoint's architecture explicitly so missing dependencies are visible.
from funasr.models.bicif_paraformer.model import BiCifParaformer

parser=argparse.ArgumentParser()
parser.add_argument('--models',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
base=args.models.resolve()
out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
# Only deserialize the fixed original image checkpoint.
with (base/'model.pt').open('rb') as handle:
 digest=hashlib.file_digest(handle, 'sha256').hexdigest()
assert digest == 'fd7c1c6fa7f499377d238b3f3790eb2f6f16318a0e33e33ae50936725f4d8388', 'Unexpected Paraformer checkpoint'
for name in ['config.yaml', 'am.mvn', 'tokens.json']:
 shutil.copy2(base/name, out/name)
torch.set_num_threads(8)
torch.backends.cuda.matmul.allow_tf32=False
torch.backends.cudnn.allow_tf32=False
model=AutoModel(model=str(base),device='cpu',disable_update=True,disable_pbar=True,ignore_init_mismatch=False)
ckpt=torch.load(base/'model.pt',map_location='cpu',weights_only=False)
for key in ['state_dict','model_state_dict','model']:
 if key in ckpt:ckpt=ckpt[key]
expected=model.model.state_dict()
missing=[];different=[];matched=0
for name,value in expected.items():
 key=name if name in ckpt else 'module.'+name
 if key not in ckpt:missing.append(name)
 elif not torch.equal(value,ckpt[key]):different.append(name)
 else:matched+=1
assert not missing and not different,(missing,different)
print(json.dumps({'checkpoint_keys':len(ckpt),'model_keys':len(expected),'matched':matched}),flush=True)
kwargs=copy.deepcopy(model.kwargs);kwargs.pop('model',None)
kwargs.update(type='torchscript',device='cpu',max_seq_len=10000)
network=model.model.eval().export(**kwargs)
if isinstance(network,(tuple,list)):assert len(network)==1;network=network[0]
inputs=network.export_dummy_inputs()
def portable_devices(module):
 graph=module.graph
 def nodes(block):
  for node in block.nodes():
   yield node
   for nested in node.blocks():yield from nodes(nested)
 constants=[n for n in nodes(graph) if n.kind()=='prim::Constant' and n.outputsSize()==1 and n.output().type().kind()=='DeviceObjType' and str(n.output().toIValue())=='cpu']
 if constants:
  device=graph.create('prim::device',[list(graph.inputs())[1]],1)
  device.output().setType(torch._C.DeviceObjType.get());device.insertBefore(next(iter(graph.nodes())))
  for node in constants:node.output().replaceAllUsesWith(device.output());node.destroy()
 torch._C._jit_pass_lint(graph)
 return len(constants)

with torch.inference_mode():
 traced=torch.jit.freeze(torch.jit.trace(network,inputs,check_trace=True).eval())
 device_constants=portable_devices(traced)
 traced.save(str(out/'model.torchscript'))
 cases=[]
 torch.manual_seed(684)
 for batch,time_length in [(1,30),(1,83),(1,250),(2,60)]:
  x=torch.randn(batch,time_length,560);lengths=torch.full((batch,),time_length,dtype=torch.int32)
  expected_outputs=network(x,lengths);actual=traced(x,lengths)
  metrics=[]
  for a,b in zip(actual,expected_outputs):
   assert a.shape==b.shape
   e=(a-b).abs()
   metrics.append({'shape':list(a.shape),'max_abs':e.max().item() if e.numel() else 0,'allclose':torch.allclose(a,b,atol=1e-5,rtol=1e-4)})
  cases.append({'batch':batch,'time':time_length,'outputs':metrics})
 report={'checkpoint_sha256':digest,'checkpoint_tensors_matched':matched,'cpu_device_constants_made_dynamic':device_constants,'architecture_revision':'df24be289221a37b55f9853d2083cf5a0a5382dc','cases':cases,'passed':all(m['allclose'] for c in cases for m in c['outputs'])}
 (out/'export-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2),flush=True)
 assert report['passed']
