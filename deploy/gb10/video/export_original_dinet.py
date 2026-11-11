"""Export the hash-pinned, original Duix DINet network without changing its graph.

Run under x86_64 CPython 3.9. The original extension and original bytecode are
loaded separately and compared before tracing the original extension. This is
an offline model conversion; it does not load or modify the service/licensing
layer. The checkpoint is trusted only after its exact official SHA256 matches.
"""
import argparse
import gc
import hashlib
import importlib.machinery
import importlib.util
import json
import platform
import sys
import time
import types
from pathlib import Path

import numpy as np
import torch


PINNED = {
    "checkpoint": "9c4568b1f1f2890b4a92edc3f9457af63f908065961233af2125d060cb56fd9e",
    "extension": "201fa990353e5b5e4f3ec7724ee04498e84b186ef87a0194a26b9a7e89b087bb",
    "bytecode": "26dfd928a4bef940dffb318f48e806532ee3c50f537f2f8fc07e0944dd4b1dc8",
}


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def pin(path, kind):
    actual = digest(path)
    if actual != PINNED[kind]:
        raise RuntimeError("Refusing unrecognized {}: {}".format(kind, actual))
    return {"path": str(path.resolve()), "bytes": path.stat().st_size,
            "sha256": actual}


def namespace(name, path):
    # Skip unrelated training-model __init__.py imports. The original network
    # itself and its original synchronized BatchNorm extension remain intact.
    mod = types.ModuleType(name)
    mod.__path__ = [str(path)]
    mod.__package__ = name
    sys.modules[name] = mod


def load_original_modules(code_root):
    namespace("landmark2face_wy", code_root / "landmark2face_wy")
    namespace("landmark2face_wy.models", code_root / "landmark2face_wy/models")
    root = code_root / "landmark2face_wy/models"
    so = root / "DINet.cpython-39-x86_64-linux-gnu.so"
    pyc = root / "__pycache__/DINet.cpython-39.pyc"
    provenance = {"extension": pin(so, "extension"), "bytecode": pin(pyc, "bytecode")}
    modules = []
    for name, path, loader_class in (
        ("landmark2face_wy.models.DINet", so, importlib.machinery.ExtensionFileLoader),
        ("landmark2face_wy.models.DINet_bytecode", pyc, importlib.machinery.SourcelessFileLoader),
    ):
        loader = loader_class(name, str(path))
        spec = importlib.util.spec_from_loader(name, loader)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        loader.exec_module(module)
        modules.append(module)
    return modules, provenance


def difference(expected, actual):
    delta = (expected - actual).abs()
    return {"max_abs": float(delta.max()), "mean_abs": float(delta.mean()),
            "rmse": float(delta.square().mean().sqrt()),
            "equal": bool(torch.equal(expected, actual)),
            "allclose_atol_1e-6_rtol_1e-5": bool(torch.allclose(expected, actual, atol=1e-6, rtol=1e-5))}


def safe_metadata(value):
    if isinstance(value, np.ndarray):
        return torch.from_numpy(value.copy())
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {k: safe_metadata(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return tuple(safe_metadata(v) for v in value)
    if isinstance(value, list):
        return [safe_metadata(v) for v in value]
    return value


def portable_devices(module):
    """Make traced tensor allocations follow the input device, without math edits.

    Original make_coordinate_grid_3d uses .type(feature_map.type()), which
    otherwise records an explicit CPU device during CPU tracing. Parameters
    and tensor constants are relocated by torch.jit.load(map_location=...).
    """
    graph = module.graph

    def nodes(block):
        for node in block.nodes():
            yield node
            for nested in node.blocks():
                yield from nodes(nested)

    candidates = []
    for node in nodes(graph):
        if node.kind() != "prim::Constant" or node.outputsSize() != 1:
            continue
        output = node.output()
        if output.type().kind() == "DeviceObjType" and str(output.toIValue()) == "cpu":
            candidates.append(node)
    if not candidates:
        return 0
    # In a frozen module forward inputs are self, source_img, ref_img, audio.
    device = graph.create("prim::device", [list(graph.inputs())[1]], 1)
    device.output().setType(torch._C.DeviceObjType.get())
    device.insertBefore(next(iter(graph.nodes())))
    for node in candidates:
        node.output().replaceAllUsesWith(device.output())
        node.destroy()
    torch._C._jit_pass_lint(graph)
    return len(candidates)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--code-root", type=Path, required=True)
    p.add_argument("--checkpoint", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--audio-length", type=int, default=20)
    p.add_argument("--threads", type=int, default=4)
    p.add_argument("--inspect-only", action="store_true")
    args = p.parse_args()
    if sys.version_info[:2] != (3, 9) or platform.machine() != "x86_64":
        raise RuntimeError("Original extension export requires x86_64 CPython 3.9")
    torch.set_num_threads(args.threads)
    # Tracing embeds cudnn's allow_tf32 argument in aten::_convolution;
    # disabling it only at GPU load time does not override that graph constant.
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.manual_seed(20261111)
    args.output.mkdir(parents=True, exist_ok=True)
    report = {"python": sys.version, "machine": platform.machine(), "torch": torch.__version__,
              "numpy": np.__version__, "threads": args.threads, "trace_allow_tf32": False,
              "scope": "Original DINet network only; full video/audio pipeline is separately validated."}
    start = time.perf_counter()

    def progress(stage):
        report["stage"] = stage
        report["elapsed_seconds"] = round(time.perf_counter() - start, 3)
        (args.output / "export-report.json").write_text(json.dumps(report, indent=2))
        print(json.dumps({"stage": stage, "elapsed_seconds": report["elapsed_seconds"]}), flush=True)

    modules, provenance = load_original_modules(args.code_root.resolve())
    report["provenance"] = provenance
    report["classes"] = [[n for n in dir(module) if n.startswith("DINet")] for module in modules]
    progress("original extension and bytecode imported")
    if args.inspect_only:
        return
    if args.checkpoint is None:
        p.error("--checkpoint is required unless --inspect-only")

    report["provenance"]["checkpoint"] = pin(args.checkpoint, "checkpoint")
    # This one fixed official checkpoint includes NumPy mask metadata. No generic
    # unsafe-load fallback: a different file digest is rejected before unpickling.
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    report["checkpoint_load"] = "weights_only=False for exact SHA256-pinned official checkpoint with NumPy masks"
    model_name = checkpoint["model_name"]
    classes = {"dinet_v1": "DINetV1", "dinet_512": "DINetMouth512"}
    if model_name not in classes:
        raise RuntimeError("Model not in original networks.define_G mapping: " + str(model_name))
    class_name = classes[model_name]
    size = int(checkpoint["model_input_size"][0])
    report["checkpoint_metadata"] = {
        "model_name": model_name, "class": class_name, "model_input_size": list(checkpoint["model_input_size"]),
        "model_ngf": int(checkpoint["model_ngf"]), "state_dict_keys": len(checkpoint["face_G"]),
        "audio_length": args.audio_length,
        "metadata_keys": list(checkpoint),
    }
    models = []
    for module in modules:
        # Exact constructor from original networks.pyc define_G('dinet_v1').
        model = getattr(module, class_name)(source_channel=3, ref_channel=3, audio_channel=256)
        incompatible = model.load_state_dict(checkpoint["face_G"], strict=True)
        assert not incompatible.missing_keys and not incompatible.unexpected_keys
        models.append(model.eval())
    report["strict_state_dict_load"] = True
    report["state_dict_transform"] = "none"
    metadata = {k: v for k, v in checkpoint.items() if k != "face_G"}
    # Converted metadata uses only tensors and primitives, so ARM consumers can
    # load it with weights_only=True; original masks retain dtype and values.
    metadata = safe_metadata(metadata)
    torch.save(metadata, args.output / "original-metadata.pt")
    reloaded_metadata = torch.load(args.output / "original-metadata.pt", map_location="cpu", weights_only=True)
    for key in ("input_mask", "input_mask_re", "fuse_mask"):
        assert torch.equal(metadata[key], reloaded_metadata[key])
        assert metadata[key].dtype == reloaded_metadata[key].dtype
    report["metadata_weights_only_reload"] = True
    del checkpoint
    gc.collect()
    progress("original checkpoint strictly loaded into both models")

    original, bytecode = models
    cases = []
    report["eager_extension_vs_bytecode"] = []
    # Two independent batch-one inputs plus a batch-two input test that the
    # traced graph does not bake in the exemplar batch size.
    for seed, batch in [(17, 1), (83, 1), (211, 2)]:
        gen = torch.Generator().manual_seed(seed)
        source = torch.rand((batch, 3, size, size), generator=gen)
        reference = torch.rand((batch, 3, size, size), generator=gen)
        audio = torch.randn((batch, 256, args.audio_length), generator=gen)
        inputs = (source, reference, audio)
        with torch.inference_mode():
            expected = original(*inputs)
            pyc_output = bytecode(*inputs)
        metrics = difference(expected, pyc_output)
        item = {"seed": seed, "batch": batch, "input_shapes": [list(x.shape) for x in inputs],
                "output_shape": list(expected.shape), **metrics}
        report["eager_extension_vs_bytecode"].append(item)
        if not metrics["allclose_atol_1e-6_rtol_1e-5"]:
            progress("FAILED original extension vs bytecode")
            raise AssertionError(item)
        cases.append({"seed": seed, "inputs": inputs, "expected": expected})
        progress("validated original extension vs bytecode seed {}".format(seed))
    torch.save(cases, args.output / "validation-vectors.pt")
    del bytecode, models, pyc_output
    gc.collect()

    # The trace is generated by the original Cython extension's forward method.
    # Validation is explicit below; check_trace=False avoids duplicate opaque
    # forwards and retains individual numerical evidence for every input case.
    with torch.inference_mode():
        traced = torch.jit.trace(original, cases[0]["inputs"], strict=True, check_trace=False)
        traced = torch.jit.freeze(traced.eval())
    (args.output / "original-cpu-graph.txt").write_text(str(traced.graph))
    report["device_adaptation"] = {
        "cpu_device_constants_replaced": portable_devices(traced),
        "replacement": "prim::device(source_img); no tensor math or parameter changes",
        "gpu_loading": "torch.jit.load(path, map_location='cuda').eval(); frozen constants must be relocated at load",
    }
    (args.output / "portable-graph.txt").write_text(str(traced.graph))
    export_path = args.output / "original-dinet.ts.pt"
    torch.jit.save(traced, str(export_path))
    del traced, original
    gc.collect()
    reloaded = torch.jit.load(str(export_path), map_location="cpu").eval()
    report["eager_extension_vs_saved_torchscript"] = []
    for case in cases:
        with torch.inference_mode():
            actual = reloaded(*case["inputs"])
        metrics = difference(case["expected"], actual)
        item = {"seed": case["seed"], "batch": int(case["inputs"][0].shape[0]), **metrics}
        report["eager_extension_vs_saved_torchscript"].append(item)
        if not metrics["allclose_atol_1e-6_rtol_1e-5"]:
            progress("FAILED original extension vs saved TorchScript")
            raise AssertionError(item)
        progress("validated saved TorchScript seed {}".format(case["seed"]))
    report["export"] = {"path": str(export_path.resolve()), "sha256": digest(export_path),
                        "bytes": export_path.stat().st_size}
    report["graph_operator_names"] = sorted(set(torch.jit.export_opnames(reloaded)))
    report["completed"] = True
    progress("complete")


if __name__ == "__main__":
    main()
