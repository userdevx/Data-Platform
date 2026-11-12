import importlib.util
from pathlib import Path
import tempfile
import unittest

try:
    from engine.application_generation import aider_adapter as aider
except ImportError:
    spec = importlib.util.spec_from_file_location("aider_adapter", Path(__file__).with_name("aider_adapter.py"))
    aider = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(aider)

class TestAiderAdapter(unittest.TestCase):
    def test_root_and_symlink_rejection(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            work = root / "work"
            work.mkdir()
            self.assertTrue(aider.in_root(work, root))
            self.assertFalse(aider.in_root(root, root))
            self.assertEqual(aider.relative_file(work, "tests/test_main.py"), "tests/test_main.py")
            for name in ("../oops.py", "/etc/passwd", "tests/../../a.py"):
                with self.assertRaises(ValueError):
                    aider.relative_file(work, name)
            (work / "bad").symlink_to("/etc")
            with self.assertRaises(ValueError):
                aider.inventory(work)
            with self.assertRaises(ValueError):
                aider.relative_file(work, "bad/passwd")

    def test_command_no_host_project_mount_or_git_commits(self):
        with tempfile.TemporaryDirectory() as d:
            command = aider.make_command(
                workspace=Path(d), model="qwen2.5-coder:7b",
                base="http://127.0.0.1:11434", image="docker.io/paulgauthier/aider:latest",
                prompt_name=".dataworc-agent-request.txt", files=["main.py"],
                container_name="dataworc-test")
            self.assertIn("--no-auto-commits", command)
            self.assertIn("--no-suggest-shell-commands", command)
            self.assertIn("--read-only", command)
            self.assertIn("--message-file", command)
            self.assertEqual(command[-2:], ["--file", "/app/main.py"])
            with self.assertRaises(ValueError):
                aider.make_command(workspace=Path(d), model="qwen2.5-coder:7b",
                    base="https://example.com", image="image", prompt_name="req", files=[], container_name="dataworc-test")

if __name__ == "__main__":
    unittest.main()
