import unittest
from pathlib import Path
import zipfile
import tempfile

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
            self.assertTrue(path.is_file(), f"Missing sample file: {name}")
            content = path.read_text(encoding="utf-8").strip()
            self.assertGreater(len(content), 0, f"File {name} is empty")

    def test_missing_text_file_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            (SAMPLE_DIR / "missing_sample.txt").read_text(encoding="utf-8")

    def test_pdf_signature(self):
        path = SAMPLE_DIR / "sample.pdf"
        self.assertTrue(path.is_file(), "Missing sample file: sample.pdf")
        data = path.read_bytes()
        self.assertTrue(data.startswith(b"%PDF-"))

    def test_png_signature(self):
        path = SAMPLE_DIR / "sample.png"
        self.assertTrue(path.is_file(), "Missing sample file: sample.png")
        data = path.read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")

    def test_xlsx_is_openxml_zip(self):
        path = SAMPLE_DIR / "sample.xlsx"
        self.assertTrue(path.is_file(), "Missing sample file: sample.xlsx")
        with zipfile.ZipFile(path, "r") as z:
            names = set(z.namelist())
        self.assertIn("[Content_Types].xml", names)
        self.assertIn("xl/workbook.xml", names)

    def test_pptx_is_openxml_zip(self):
        path = SAMPLE_DIR / "sample.pptx"
        self.assertTrue(path.is_file(), "Missing sample file: sample.pptx")
        with zipfile.ZipFile(path, "r") as z:
            names = set(z.namelist())
        self.assertIn("[Content_Types].xml", names)
        self.assertIn("ppt/presentation.xml", names)

    def test_invalid_zip_files_raise_bad_zip_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad_xlsx = Path(tmp) / "bad.xlsx"
            bad_pptx = Path(tmp) / "bad.pptx"
            bad_xlsx.write_bytes(b"not a zip")
            bad_pptx.write_bytes(b"not a zip")

            for bad_file in (bad_xlsx, bad_pptx):
                with self.assertRaises(zipfile.BadZipFile):
                    zipfile.ZipFile(bad_file, "r")


if __name__ == "__main__":
    unittest.main()
