"""Static contract guards for iOS foreground-only wake behavior.

These checks cannot replace compiling/running the iPhone app on device.
"""
from pathlib import Path
import re
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / "ios" / "Sources"
          / "NanoANEBridge" / "ContentView.swift")


class ForegroundWakeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text(encoding="utf-8")

    def test_secure_service_enables_idle_timer_override_only_after_start(self):
        self.assertIn("import UIKit", self.source)
        start = self.source.split("private func startTLS()", 1)[1].split(
            "private func stopTLS()", 1)[0]
        self.assertRegex(start, re.compile(
            r"try server\.startExplicitly\([\s\S]*?"
            r"tlsActive = true\s+"
            r"UIApplication\.shared\.isIdleTimerDisabled = true"))

    def test_failure_and_explicit_stop_restore_locking(self):
        start = self.source.split("private func startTLS()", 1)[1].split(
            "private func stopTLS()", 1)[0]
        stop = self.source.split("private func stopTLS()", 1)[1]
        self.assertRegex(start, re.compile(
            r'if message\.hasPrefix\("TLS listener failed"\)\s*\{'
            r"[\s\S]*?tlsActive = false\s+"
            r"UIApplication\.shared\.isIdleTimerDisabled = false"))
        self.assertRegex(stop, re.compile(
            r"tlsActive = false\s+"
            r"UIApplication\.shared\.isIdleTimerDisabled = false"))

    def test_leaving_foreground_stops_service_and_resets_idle(self):
        self.assertIn("if phase != .active { stopTLS() }", self.source)
        self.assertIn("UIApplication.shared.isIdleTimerDisabled = false",
                      self.source.split("private func stopTLS()", 1)[1])


if __name__ == "__main__":
    unittest.main()
