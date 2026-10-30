"""Regression checks for device typography and retired production resources."""

import unittest
from pathlib import Path

from check_font_policy import SYSTEM_FONT_NAMES, validate_font_policy


class FontPolicyTests(unittest.TestCase):
    def setUp(self):
        self.stack = ",".join(SYSTEM_FONT_NAMES)

    def test_device_fonts_need_no_bundled_font(self):
        self.assertEqual(validate_font_policy(self.stack), [])

    def test_missing_device_fallback_is_blocked(self):
        for name in SYSTEM_FONT_NAMES:
            with self.subTest(font=name):
                self.assertTrue(validate_font_policy(self.stack.replace(name, "")))

    def test_embedded_or_downloaded_fonts_are_blocked(self):
        for css in (
            '@FONT-FACE {font-family: custom}',
            '@import "https://example.org/style.css"',
            'https://fonts.googleapis.com/css2?family=Noto',
            'https://fonts.gstatic.com/font',
            'src: url("local.woff2")',
            'src: url(https://example.org/local.ttf?v=1)',
            'src: url(data:font/woff2;base64,AAAA)',
            'src: url(data:application/x-font-ttf;base64,AAAA)',
        ):
            with self.subTest(css=css):
                self.assertTrue(validate_font_policy(self.stack + css))

    def test_current_renderer_keeps_device_typography(self):
        renderer = Path(__file__).with_name("render_wechat_html.py")
        self.assertEqual(validate_font_policy(renderer.read_text(encoding="utf-8")), [])

    def test_production_plugin_has_no_font_files_or_cover_generators(self):
        root = Path(__file__).resolve().parents[1]
        fonts = [path for path in (root / "assets").rglob("*")
                 if path.suffix.lower() in {".ttf", ".otf", ".woff", ".woff2", ".eot"}]
        self.assertEqual(fonts, [])
        for name in ("generate_test_cover.ps1", "generate_phase2_cover.ps1"):
            self.assertFalse((root / "scripts" / name).exists())
        self.assertTrue((root / "assets" / "phase1-test-cover.png").is_file())
        self.assertTrue((root / "assets" / "phase2-feature-selection-cover.png").is_file())


if __name__ == "__main__":
    unittest.main()
