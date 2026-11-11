"""Archive boundaries and Docker layer semantics without network/model downloads."""
import io
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prepare_assets import extract_layer, relative_member


class LayerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.out = self.root / "out"
        self.out.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def layer(self, entries):
        path = self.root / "layer.tgz"
        with tarfile.open(path, "w:gz") as archive:
            for name, content in entries:
                member = tarfile.TarInfo(name)
                member.size = len(content)
                archive.addfile(member, io.BytesIO(content))
        return path

    def test_whiteout_is_applied_before_new_files_even_if_tar_order_reversed(self):
        (self.out / "removed").write_text("old")
        path = self.layer([("prefix/new", b"new"), ("prefix/.wh..wh..opq", b"")])
        extract_layer(path, "prefix", self.out)
        self.assertFalse((self.out / "removed").exists())
        self.assertEqual((self.out / "new").read_bytes(), b"new")

    def test_named_whiteout_and_other_prefix(self):
        (self.out / "removed").write_text("old")
        path = self.layer([("prefix/.wh.removed", b""), ("prefix-ok/file", b"skip")])
        extract_layer(path, "prefix", self.out)
        self.assertEqual(list(self.out.iterdir()), [])

    def test_traversal_rejected(self):
        for name in ("../outside", "/absolute", "prefix/../../outside"):
            with self.assertRaises(ValueError):
                relative_member(name, "prefix")

    def test_escaping_symlink_rejected(self):
        path = self.root / "layer.tgz"
        with tarfile.open(path, "w:gz") as archive:
            member = tarfile.TarInfo("prefix/link")
            member.type = tarfile.SYMTYPE
            member.linkname = "../../outside"
            archive.addfile(member)
        with self.assertRaises(ValueError):
            extract_layer(path, "prefix", self.out)

    def test_source_skips_compiled_libraries_and_elf_executables(self):
        path = self.layer([("prefix/bin", b"\x7fELFpayload"),
                           ("prefix/module.so", b"binary"),
                           ("prefix/hello.py", b"print('hello')\n")])
        extract_layer(path, "prefix", self.out, source_only=True)
        self.assertEqual([p.name for p in self.out.iterdir()], ["hello.py"])


if __name__ == "__main__":
    unittest.main()
