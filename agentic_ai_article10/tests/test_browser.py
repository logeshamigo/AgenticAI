import threading
import unittest
from pathlib import Path
import tempfile
from unittest.mock import MagicMock
from playwright.sync_api import TimeoutError as PlaywrightTimeout, Error as PlaywrightError
from agent import PolicyDenied, OutcomeUnknown, Task, Controller, Checkpoints
from browser_adapter import PlaywrightAdapter

class TestBrowserPolicy(unittest.TestCase):
    def test_refuses_remote_origin(self):
        for u in ['https://example.com','http://localhost:9000','http://127.0.0.1.evil.com:80', 'file:///tmp/foo']:
            with self.subTest(url=u), self.assertRaises(PolicyDenied): PlaywrightAdapter(None,u)

class TestPlaywrightErrorMapping(unittest.TestCase):
    def adapter_with_failing_click(self, exc):
        page = MagicMock()
        page.get_by_role.return_value.click.side_effect = exc
        return PlaywrightAdapter(page, 'http://127.0.0.1:9000')
    def test_playwright_timeout_is_not_builtin_timeout(self):
        self.assertFalse(issubclass(PlaywrightTimeout, TimeoutError))
    def test_click_timeout_becomes_outcome_unknown(self):
        ad = self.adapter_with_failing_click(PlaywrightTimeout('Timeout 5000ms exceeded'))
        with self.assertRaises(OutcomeUnknown): ad.submit('T-104', 'Resolved')
    def test_other_playwright_error_becomes_outcome_unknown(self):
        ad = self.adapter_with_failing_click(PlaywrightError('Target closed'))
        with self.assertRaises(OutcomeUnknown): ad.submit('T-104', 'Resolved')

class TestLiveBrowserCommitThenTimeout(unittest.TestCase):
    """Real Chromium. Skipped automatically if Chromium is not installed."""
    def test_commit_then_playwright_timeout_verifies_without_resubmitting(self):
        from playwright.sync_api import sync_playwright
        from local_app import TicketServer
        server = TicketServer()
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        origin = f'http://127.0.0.1:{server.server_port}'
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception as exc:
                self.skipTest(f'Chromium unavailable: {exc}')
            try:
                page = browser.new_context().new_page()
                ad = PlaywrightAdapter(page, origin)
                real_click_submit = ad.submit
                def commit_then_timeout(ticket, status):
                    # Call the real UI path (which commits), then fail like a slow response.
                    real_click_submit(ticket, status)
                    raise OutcomeUnknown('simulated post-commit uncertainty')
                ad.submit = commit_then_timeout
                with tempfile.TemporaryDirectory() as d:
                    result = Controller(ad, Checkpoints(Path(d) / 's.json')).run(Task('T-104', 'Resolved', True))
                self.assertEqual(result, 'verified')
                self.assertEqual(page.request.get(origin + '/ticket/T-104/status').json()['writes'], 1)
            finally:
                browser.close()

if __name__ == '__main__': unittest.main()
