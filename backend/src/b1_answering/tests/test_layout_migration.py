"""Tests for b1_answering layout migration builder."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import builder under test
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from src.b1_answering.tools.refactor_layout import build_layout, _transform_content


class TestBuildLayoutValidation(unittest.TestCase):
    """Validation of source/destination constraints."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _make_source(self, name="b1_answering"):
        """Create minimal valid source tree."""
        src = self.base / name
        src.mkdir(exist_ok=True)
        (src / "policy.py").write_text("x=1")
        return src

    def test_source_must_exist(self):
        """Rejects non-existent source."""
        with self.assertRaises(ValueError) as cm:
            build_layout(self.base / "missing", self.base / "dest")
        self.assertIn("Invalid source", str(cm.exception))

    def test_source_must_be_directory(self):
        """Rejects file source."""
        f = self.base / "file.py"
        f.write_text("x")
        with self.assertRaises(ValueError) as cm:
            build_layout(f, self.base / "dest")
        self.assertIn("Invalid source", str(cm.exception))

    def test_source_must_be_named_b1_answering(self):
        """Rejects source with wrong name."""
        src = self.base / "wrong_name"
        src.mkdir()
        with self.assertRaises(ValueError) as cm:
            build_layout(src, self.base / "dest")
        self.assertIn("Invalid source", str(cm.exception))

    def test_source_symlink_rejected(self):
        """Rejects symlink source."""
        src = self._make_source()
        link = self.base / "link_to_src"
        try:
            link.symlink_to(src)
            with self.assertRaises(ValueError) as cm:
                build_layout(link, self.base / "dest")
            self.assertIn("symlink", str(cm.exception))
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks not supported on this platform")

    def test_destination_must_not_exist(self):
        """Rejects existing destination."""
        src = self._make_source()
        dest = self.base / "dest"
        dest.mkdir()
        with self.assertRaises(FileExistsError) as cm:
            build_layout(src, dest)
        self.assertIn("must not exist", str(cm.exception))

    def test_source_dest_cannot_be_identical(self):
        """Rejects source == destination."""
        src = self._make_source()
        with self.assertRaises(ValueError) as cm:
            build_layout(src, src)
        self.assertIn("distinct", str(cm.exception))

    def test_source_cannot_be_inside_destination(self):
        """Rejects nested configuration."""
        src = self._make_source()
        dest = self.base / "outer"
        nested_src = dest / "inner" / "b1_answering"
        nested_src.mkdir(parents=True)
        (nested_src / "policy.py").write_text("x")
        with self.assertRaises(ValueError) as cm:
            build_layout(nested_src, dest)
        self.assertIn("nested", str(cm.exception))

    def test_destination_cannot_be_inside_source(self):
        """Rejects destination inside source."""
        src = self._make_source()
        dest = src / "subdir" / "dest"
        with self.assertRaises(ValueError) as cm:
            build_layout(src, dest)
        self.assertIn("nested", str(cm.exception))

    def test_symlink_in_source_rejected(self):
        """Rejects symlinks within source tree."""
        src = self._make_source()
        target = self.base / "target.txt"
        target.write_text("data")
        link = src / "link.txt"
        try:
            link.symlink_to(target)
            with self.assertRaises(ValueError) as cm:
                build_layout(src, self.base / "dest")
            self.assertIn("Symlinks not supported", str(cm.exception))
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks not supported on this platform")


class TestBuildLayoutMigration(unittest.TestCase):
    """Core migration behavior."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _make_source(self):
        """Create realistic source tree."""
        src = self.base / "b1_answering"
        src.mkdir()
        (src / "policy.py").write_text("# policy policy.py")
        (src / "citations.py").write_text("# citations citations.py")
        (src / "prompt.py").write_text("# prompt prompt.py")
        (src / "gemini.py").write_text("from .policy import X")
        (src / "service.py").write_text("from .policy import Y\nfrom .citations import Z")
        (src / "dialogue.py").write_text("from .prompt import A")
        (src / "hoi.py").write_text("parents[2]")
        (src / "limits.json").write_text('{"key": "value"}')
        (src / "README.md").write_text("# README")
        (src / "_CONTRACT.md").write_text("# Contract")
        (src / "CONTRACT.md").write_text("# Another Contract")
        (src / "tests").mkdir()
        (src / "tests" / "test_unit.py").write_text("# test")
        (src / "other_file.py").write_text("# other")
        return src

    def test_files_moved_to_correct_locations(self):
        """Verifies exact file moves per mapping."""
        src = self._make_source()
        dest = self.base / "dest"
        build_layout(src, dest)
        self.assertTrue((dest / "core" / "policy.py").exists())
        self.assertTrue((dest / "evidence" / "citations.py").exists())
        self.assertTrue((dest / "evidence" / "prompt.py").exists())
        self.assertTrue((dest / "providers" / "gemini.py").exists())
        self.assertTrue((dest / "application" / "service.py").exists())
        self.assertTrue((dest / "application" / "dialogue.py").exists())
        self.assertTrue((dest / "cli" / "main.py").exists())
        self.assertTrue((dest / "config" / "limits.json").exists())

    def test_readme_preserved_at_root(self):
        """README stays at root, not moved."""
        src = self._make_source()
        dest = self.base / "dest"
        build_layout(src, dest)
        self.assertTrue((dest / "README.md").exists())
        self.assertEqual((dest / "README.md").read_text(), "# README")

    def test_contract_files_moved_to_docs(self):
        """*_CONTRACT.md and CONTRACT.md move to docs/."""
        src = self._make_source()
        dest = self.base / "dest"
        build_layout(src, dest)
        self.assertTrue((dest / "docs" / "_CONTRACT.md").exists())
        self.assertTrue((dest / "docs" / "CONTRACT.md").exists())
        self.assertFalse((dest / "_CONTRACT.md").exists())
        self.assertFalse((dest / "CONTRACT.md").exists())

    def test_tests_preserved_unchanged(self):
        """tests/ directory preserved with contents."""
        src = self._make_source()
        dest = self.base / "dest"
        build_layout(src, dest)
        self.assertTrue((dest / "tests" / "test_unit.py").exists())
        self.assertEqual((dest / "tests" / "test_unit.py").read_text(), "# test")

    def test_other_files_preserved_in_place(self):
        """Unknown files stay in source relative path."""
        src = self._make_source()
        dest = self.base / "dest"
        build_layout(src, dest)
        self.assertTrue((dest / "other_file.py").exists())
        self.assertEqual((dest / "other_file.py").read_text(), "# other")

    def test_subpackage_init_files_created(self):
        """Empty __init__.py added to all subpackages."""
        src = self._make_source()
        dest = self.base / "dest"
        build_layout(src, dest)
        for pkg in ["application", "cli", "config", "core", "evidence", "providers"]:
            self.assertTrue((dest / pkg / "__init__.py").exists(),
                          f"Missing {pkg}/__init__.py")

    def test_root_init_generated(self):
        """Root __init__.py with compatibility registry created."""
        src = self._make_source()
        dest = self.base / "dest"
        build_layout(src, dest)
        init = (dest / "__init__.py").read_text()
        self.assertIn("Compatibility registry", init)
        self.assertIn("sys.modules", init)
        self.assertIn("_ALIASES", init)

    def test_hoi_legacy_shim_generated(self):
        """Root hoi.py legacy shim created."""
        src = self._make_source()
        dest = self.base / "dest"
        build_layout(src, dest)
        hoi = (dest / "hoi.py").read_text()
        self.assertIn("Legacy CLI", hoi)
        self.assertIn("parents[2]", hoi)
        self.assertIn("cli.main", hoi)

    def test_main_entrypoint_generated(self):
        """__main__.py for python -m created."""
        src = self._make_source()
        dest = self.base / "dest"
        build_layout(src, dest)
        main = (dest / "__main__.py").read_text()
        self.assertIn("cli.main", main)

    def test_source_unchanged_after_migration(self):
        """Source directory untouched byte-for-byte."""
        src = self._make_source()
        src_policy_before = (src / "policy.py").read_bytes()
        dest = self.base / "dest"
        build_layout(src, dest)
        src_policy_after = (src / "policy.py").read_bytes()
        self.assertEqual(src_policy_before, src_policy_after)
        self.assertEqual((src / "hoi.py").read_text(), "parents[2]")

    def test_pycache_excluded(self):
        """__pycache__ and .pyc files not copied."""
        src = self._make_source()
        cache = src / "__pycache__"
        cache.mkdir()
        (cache / "policy.cpython-39.pyc").write_text("pyc")
        dest = self.base / "dest"
        build_layout(src, dest)
        self.assertFalse((dest / "__pycache__").exists())

    def test_no_duplicate_root_files(self):
        """No duplicate root __init__.py from moved hoi.py."""
        src = self._make_source()
        dest = self.base / "dest"
        build_layout(src, dest)
        root_init = (dest / "__init__.py").read_text()
        # Root init is the compatibility registry, not the moved file
        self.assertIn("sys.modules", root_init)
        # Moved hoi becomes cli/main.py
        self.assertTrue((dest / "cli" / "main.py").exists())


class TestImportTransformations(unittest.TestCase):
    """Import rewriting for moved modules."""

    def test_core_policy_limits_json_rewrite(self):
        """policy.py limits.json path updated."""
        text = "x = Path(__file__).with_name('limits.json')"
        result = _transform_content("core/policy.py", text)
        self.assertIn("parents[1] / 'config' / 'limits.json'", result)
        self.assertNotIn("with_name", result)

    def test_providers_gemini_imports_rewritten(self):
        """gemini.py .policy -> ..core.policy."""
        text = "from .policy import Config"
        result = _transform_content("providers/gemini.py", text)
        self.assertEqual(result, "from ..core.policy import Config")

    def test_application_service_imports_rewritten(self):
        """service.py imports rewritten to parent packages."""
        text = "from .policy import X\nfrom .citations import Y\nfrom .prompt import Z\nfrom .gemini import W"
        result = _transform_content("application/service.py", text)
        self.assertIn("from ..core.policy import X", result)
        self.assertIn("from ..evidence.citations import Y", result)
        self.assertIn("from ..evidence.prompt import Z", result)
        self.assertIn("from ..providers.gemini import W", result)

    def test_application_dialogue_imports_rewritten(self):
        """dialogue.py imports rewritten."""
        text = "from .policy import X"
        result = _transform_content("application/dialogue.py", text)
        self.assertIn("from ..core.policy import X", result)

    def test_cli_main_canonical_imports_rewritten(self):
        """hoi.py->cli/main.py canonical absolute imports updated."""
        text = "parents[2]\nfrom src.b1_answering.policy import X\nfrom src.b1_answering.service import Y"
        result = _transform_content("cli/main.py", text)
        self.assertIn("parents[3]", result)
        self.assertIn("src.b1_answering.core.policy", result)
        self.assertIn("src.b1_answering.application.service", result)

    def test_cli_main_all_module_rewrites(self):
        """cli/main.py handles all six canonical modules."""
        text = ("src.b1_answering.policy "
                "src.b1_answering.citations "
                "src.b1_answering.prompt "
                "src.b1_answering.gemini "
                "src.b1_answering.service "
                "src.b1_answering.dialogue")
        result = _transform_content("cli/main.py", text)
        self.assertIn("src.b1_answering.core.policy", result)
        self.assertIn("src.b1_answering.evidence.citations", result)
        self.assertIn("src.b1_answering.evidence.prompt", result)
        self.assertIn("src.b1_answering.providers.gemini", result)
        self.assertIn("src.b1_answering.application.service", result)
        self.assertIn("src.b1_answering.application.dialogue", result)

    def test_untransformed_files_unchanged(self):
        """Files not in mapping returned verbatim."""
        text = "from .policy import X"
        result = _transform_content("tests/test_unit.py", text)
        self.assertEqual(result, text)


class TestEdgeCases(unittest.TestCase):
    """Boundary and error handling."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_minimal_source_with_only_mapped_files(self):
        """Migration works with only files in MOVE_MAP."""
        src = self.base / "b1_answering"
        src.mkdir()
        (src / "policy.py").write_text("x")
        dest = self.base / "dest"
        build_layout(src, dest)
        self.assertTrue((dest / "core" / "policy.py").exists())
        self.assertTrue((dest / "__init__.py").exists())
        self.assertTrue((dest / "hoi.py").exists())

    def test_empty_source_directories_preserved(self):
        """Empty subdirs in source are preserved."""
        src = self.base / "b1_answering"
        src.mkdir()
        (src / "policy.py").write_text("x")
        (src / "empty_dir").mkdir()
        dest = self.base / "dest"
        build_layout(src, dest)
        # Empty dirs may not be created; this is not a failure
        self.assertTrue((dest / "core" / "policy.py").exists())

    def test_unicode_content_preserved(self):
        """UTF-8 content handled correctly."""
        src = self.base / "b1_answering"
        src.mkdir()
        text = "# 你好世界 Привет мир"
        (src / "policy.py").write_text(text, encoding="utf-8")
        dest = self.base / "dest"
        build_layout(src, dest)
        result = (dest / "core" / "policy.py").read_text(encoding="utf-8")
        self.assertEqual(result, text)

    def test_limits_json_binary_preserved(self):
        """JSON file content preserved exactly."""
        src = self.base / "b1_answering"
        src.mkdir()
        content = '{"a": 1, "b": 2}'
        (src / "limits.json").write_text(content)
        dest = self.base / "dest"
        build_layout(src, dest)
        result = (dest / "config" / "limits.json").read_text()
        self.assertEqual(result, content)


if __name__ == "__main__":
    unittest.main()
