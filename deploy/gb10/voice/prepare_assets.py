#!/usr/bin/env python3
"""Fetch pinned upstream inputs outside Git; never run code from an image layer."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
import tempfile
import time
import urllib.request
import zipfile

HERE = Path(__file__).resolve().parent
SOURCES = json.loads((HERE / "sources.json").read_text())


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch(name, cache):
    spec = SOURCES[name]
    target = cache / (spec["sha256"] + spec.get("suffix", ".tar.gz"))
    if target.exists():
        if sha256(target) != spec["sha256"]:
            raise ValueError(f"Cached checksum mismatch: {target.name}")
        return target
    partial = target.with_suffix(target.suffix + ".part")
    for attempt in range(4):
        headers = {}
        if "repository" in spec:
            auth = "https://auth.docker.io/token?service=registry.docker.io&scope=repository:" + spec["repository"] + ":pull"
            with urllib.request.urlopen(auth, timeout=30) as response:
                headers["Authorization"] = "Bearer " + json.load(response)["token"]
        offset = partial.stat().st_size if partial.exists() else 0
        if offset:
            headers["Range"] = f"bytes={offset}-"
        try:
            with urllib.request.urlopen(urllib.request.Request(spec["url"], headers=headers), timeout=90) as response:
                resumed = offset and response.status == 206
                if resumed and not response.headers.get("Content-Range", "").startswith(f"bytes {offset}-"):
                    raise ValueError("Unexpected download range")
                with partial.open("ab" if resumed else "wb") as output:
                    shutil.copyfileobj(response, output, 1024 * 1024)
            if partial.stat().st_size != spec["bytes"] or sha256(partial) != spec["sha256"]:
                partial.unlink()
                raise ValueError(f"Download checksum/size mismatch: {name}")
            partial.replace(target)
            return target
        except (OSError, ValueError):
            if attempt == 3:
                raise
            time.sleep(1 + attempt)
    raise RuntimeError(name)


def relative_member(name, prefix):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Unsafe archive member")
    clean = path.as_posix().removeprefix("./")
    prefix = prefix.rstrip("/")
    if clean == prefix:
        return Path(".")
    if not clean.startswith(prefix + "/"):
        return None
    return Path(clean[len(prefix) + 1:])


def remove(path):
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def extract_layer(archive, prefix, destination, source_only=False):
    """Apply OCI whiteouts before upper-layer entries, independent of tar order."""
    destination.mkdir(parents=True, exist_ok=True)
    # A whiteout removes lower-layer entries, never a new entry from this layer.
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar:
            rel = relative_member(member.name, prefix)
            if rel is None or not rel.name.startswith(".wh."):
                continue
            parent = destination / rel.parent
            if rel.name == ".wh..wh..opq":
                if parent.is_dir():
                    for child in parent.iterdir():
                        remove(child)
            else:
                remove(parent / rel.name[4:])
    with tarfile.open(archive, "r:gz") as tar:
        links = []
        for member in tar:
            rel = relative_member(member.name, prefix)
            if rel is None or rel == Path(".") or rel.name.startswith(".wh."):
                continue
            if any(p in {".git", "__pycache__"} for p in rel.parts):
                continue
            if source_only and prefix == "workspace/FunASR":
                # Only the Python exporter and C++ offline server are used.
                # Other examples contain developer-machine absolute links.
                selected = (rel.parts[0] == "funasr" or
                            rel.parts[:2] in (("runtime", "websocket"), ("runtime", "onnxruntime")) or
                            rel.name in {"LICENSE", "README.md", "setup.py"})
                if not selected or "build" in rel.parts:
                    continue
            if source_only and (".so" in rel.name or rel.suffix in {".a", ".o", ".pyc"}):
                continue
            target = destination / rel
            # Existing links can never redirect extraction outside this tree.
            for parent in target.parents:
                if parent == destination:
                    break
                if parent.is_symlink():
                    raise ValueError("Symlink parent in archive")
            target.parent.mkdir(parents=True, exist_ok=True)
            if member.isdir():
                if target.is_symlink() or target.is_file():
                    remove(target)
                target.mkdir(exist_ok=True)
            elif member.isfile():
                if target.exists() or target.is_symlink():
                    remove(target)
                with tar.extractfile(member) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
                if source_only:
                    with target.open("rb") as check:
                        magic = check.read(8)
                    if magic.startswith(b"\x7fELF") or magic == b"!<arch>\n":
                        target.unlink()
                        continue
                target.chmod(member.mode & 0o777)
            elif member.issym():
                # Source archives may use relative links; disallow escaping ones.
                if os.path.isabs(member.linkname):
                    raise ValueError("Absolute archive symlink")
                resolved = (target.parent / member.linkname).resolve()
                if not resolved.is_relative_to(destination.resolve()):
                    raise ValueError("Escaping archive symlink")
                links.append((target, member.linkname))
            elif member.islnk():
                linked = relative_member(member.linkname, prefix)
                if linked is None:
                    raise ValueError("Escaping archive hardlink")
                links.append((target, os.path.relpath(destination / linked, target.parent)))
        for target, linked in links:
            if target.exists() or target.is_symlink():
                remove(target)
            target.symlink_to(linked)


def patch(root, filename):
    subprocess.run(["patch", "--batch", "--forward", "-p1", "-i", str(HERE / "patches" / filename)], cwd=root, check=True)


def prepare_tree(output, name, build):
    target = output / name
    stamp = target / ".duix-prepared.json"
    recipe = sha256(HERE / "sources.json") + sha256(Path(__file__))
    for path in sorted((HERE / "patches").glob("*.patch")):
        recipe += sha256(path)
    if stamp.exists() and json.loads(stamp.read_text())["recipe"] == recipe:
        print(f"Already prepared: {name}", flush=True)
        return
    if target.exists():
        raise ValueError(f"Refusing to overwrite {target}; move it aside to re-prepare")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".prepare-", dir=target.parent) as temp:
        stage = Path(temp) / "tree"
        stage.mkdir()
        build(stage)
        (stage / ".duix-prepared.json").write_text(json.dumps({"recipe": recipe}, indent=2) + "\n")
        stage.rename(target)


def prepare(args):
    output = args.output.resolve()
    cache = (args.cache or output / "downloads").resolve()
    cache.mkdir(parents=True, exist_ok=True)
    component = args.component
    if component in {"all", "fish"}:
        def fish(stage):
            extract_layer(fetch("fish_source", cache), SOURCES["fish_source"]["prefix"], stage, True)
            extract_layer(fetch("fish_image_37", cache), "code/tools/text_norm", stage / "tools/text_norm", True)
            patch(stage, "fish-arm.patch")
            patch(stage, "text-normalizer-arm.patch")
            with zipfile.ZipFile(fetch("nltk_words", cache)) as archive:
                destination = stage / "tools/text_norm/nltk_data/corpora"
                for member in archive.infolist():
                    rel = relative_member(member.filename, "words")
                    if rel is None or member.is_dir():
                        continue
                    target = destination / "words" / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(member) as source, target.open("wb") as out:
                        shutil.copyfileobj(source, out)
        prepare_tree(output, "fish-speech", fish)
        if not args.sources_only:
            prepare_tree(output, "models/fish-speech-1.5", lambda stage: extract_layer(fetch("fish_image_37", cache), "code/checkpoints/fish-speech-1.5", stage))
    if component in {"all", "asr"}:
        def asr(stage):
            for number in (29, 30, 32, 34):
                extract_layer(fetch(f"asr_image_{number}", cache), "workspace/FunASR", stage, True)
            if not (stage / "runtime/websocket/bin/funasr-wss-server.cpp").exists():
                raise ValueError("Incomplete original FunASR source")
        prepare_tree(output, "FunASR", asr)
        prepare_tree(output, "deps/onnxruntime-linux-aarch64-1.20.1", lambda stage: extract_layer(fetch("onnxruntime", cache), "onnxruntime-linux-aarch64-1.20.1", stage))
        if not args.sources_only:
            prepare_tree(output, "models/asr/original", lambda stage: extract_layer(fetch("asr_image_36", cache), "workspace/models", stage))
    if component in {"all", "rnnoise"}:
        def rnnoise(stage):
            extract_layer(fetch("rnnoise_source", cache), SOURCES["rnnoise_source"]["prefix"], stage, True)
            with tempfile.TemporaryDirectory(dir=output) as tmp:
                cli = Path(tmp)
                extract_layer(fetch("rnnoise_cli", cache), SOURCES["rnnoise_cli"]["prefix"], cli, True)
                for filename in ("rnnoise_demo.c", "dr_wav.h", "dr_mp3.h"):
                    shutil.copy2(cli / "examples" / filename, stage / filename)
                shutil.copy2(cli / "COPYING", stage / "COPYING-cpuimage")
            patch(stage, "rnnoise-cli.patch")
        prepare_tree(output, "rnnoise", rnnoise)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE.parent / "assets/voice")
    parser.add_argument("--cache", type=Path, help="Directory of downloaded SHA-named archives")
    parser.add_argument("--component", choices=("all", "fish", "asr", "rnnoise"), default="all")
    parser.add_argument("--sources-only", action="store_true", help="Skip separate runtime model directories")
    prepare(parser.parse_args())
