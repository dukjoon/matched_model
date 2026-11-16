import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from matched_model.cli import main


REPO_ROOT = Path(__file__).resolve().parents[1]


class TestCLI(unittest.TestCase):
    def test_cli_recommend_json(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["--root", str(REPO_ROOT), "recommend", "--phase", "implement", "--complexity", "medium", "--json"])
        self.assertEqual(rc, 0)
        data = json.loads(buf.getvalue())
        self.assertEqual(data["profile_used"], "implement")
        self.assertIsNotNone(data["primary"])

    def test_cli_plan_check(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as tmp:
            tmp.write("- Design core authentication architecture\n- Update README typos\n")
            tmp_path = tmp.name
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["--root", str(REPO_ROOT), "plan-check", "--file", tmp_path, "--json"])
        self.assertEqual(rc, 0)
        rows = json.loads(buf.getvalue())
        self.assertEqual(len(rows), 2)


if __name__ == "__main__":
    unittest.main()
