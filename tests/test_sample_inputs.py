import unittest
from pathlib import Path
import zipfile

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR = REPO_ROOT / "sample_input"


class TestSampleInputs(unittest.TestCase):
    def test_required_sample_files_exist(self):
        expected = {
            "sample.txt",
            "sample.md",
            "sample.pdf",
            "sample.png",
            "sample.xlsx",
            "sample.pptx",
        }
        actual = {p.name for p in SAMPLE_DIR.iterdir() if p.is_file()}
        self.assertTrue(expected.issubset(actual))

    def test_text_files_are_readable(self):
        for name in ("sample.txt", "sample.md"):
            path = SAMPLE_DIR / name
            content = path.read_text(encoding="utf-8").strip()
            self.assertTrue(content)

    def test_pdf_signature(self):
        data = (SAMPLE_DIR / "sample.pdf").read_bytes()
        self.assertTrue(data.startswith(b"%PDF-"))

    def test_png_signature(self):
        data = (SAMPLE_DIR / "sample.png").read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")

    def test_xlsx_is_openxml_zip(self):
        with zipfile.ZipFile(SAMPLE_DIR / "sample.xlsx", "r") as z:
            names = set(z.namelist())
        self.assertIn("[Content_Types].xml", names)
        self.assertIn("xl/workbook.xml", names)

    def test_pptx_is_openxml_zip(self):
        with zipfile.ZipFile(SAMPLE_DIR / "sample.pptx", "r") as z:
            names = set(z.namelist())
        self.assertIn("[Content_Types].xml", names)
        self.assertIn("ppt/presentation.xml", names)


if __name__ == "__main__":
    unittest.main()
