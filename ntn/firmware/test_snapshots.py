import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
import re

EXCLUDED = ["overlay-memfault.conf", "overlay-upload-modem-traces-to-memfault.conf",
            "overlay-guardiansat.conf"]
FORBIDDEN = [re.compile(r"187\.102\.3\.112"),
             re.compile(r'MEMFAULT_NCS_PROJECT_KEY="[^"]+"'),   # chave preenchida
             re.compile(r"N2YO_API_KEY\s*=\s*\"[^\"]+\"")]


class SnapshotTest(unittest.TestCase):
    def _files(self, which):
        root = os.path.join(HERE, which, "app")
        self.assertTrue(os.path.isdir(root), root)
        for d, _, fs in os.walk(root):
            for f in fs:
                yield os.path.join(d, f)

    def test_excluded_files_absent(self):
        for which in ["geo", "leo"]:
            names = {os.path.basename(p) for p in self._files(which)}
            for ex in EXCLUDED:
                self.assertNotIn(ex, names, f"{which}: {ex}")

    def test_no_customer_endpoint_or_keys(self):
        for which in ["geo", "leo"]:
            for p in self._files(which):
                if p.endswith((".conf", ".c", ".h", ".yml", ".yaml", ".md", ".txt")):
                    with open(p, encoding="utf-8", errors="replace") as fh:
                        s = fh.read()
                    for bad in FORBIDDEN:
                        self.assertIsNone(bad.search(s), f"{p}: {bad.pattern}")

    def test_ntn_module_present(self):
        for which in ["geo", "leo"]:
            self.assertTrue(os.path.exists(os.path.join(HERE, which, "app", "src", "modules", "ntn", "ntn.c")))
            self.assertTrue(os.path.exists(os.path.join(HERE, which, "README.md")))
