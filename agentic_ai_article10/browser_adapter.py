"""Playwright adapter: semantic UI locators for actions, local app for verification."""
from urllib.parse import urlparse
from playwright.sync_api import Page, Error as PlaywrightError
from agent import PolicyDenied, OutcomeUnknown

class PlaywrightAdapter:
    def __init__(self, page: Page, base_url: str):
        parsed = urlparse(base_url)
        if parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or parsed.port is None or parsed.username or parsed.password:
            raise PolicyDenied('Only explicit 127.0.0.1 local app origin is allowed')
        self.page = page
        self.base_url = base_url.rstrip('/')
    def _path(self, ticket_id):
        if ticket_id != 'T-104': raise PolicyDenied('Ticket not allowed')
        return f'/ticket/{ticket_id}'
    def observe(self, ticket_id):
        self.page.goto(self.base_url + self._path(ticket_id), wait_until='domcontentloaded', timeout=5000)
        return self.page.get_by_test_id('ticket-status').inner_text(timeout=5000).strip()
    def submit(self, ticket_id, status):
        self._path(ticket_id)
        if status not in {'Open', 'In Progress', 'Resolved'}: raise PolicyDenied('Status not allowed')
        try:
            self.page.get_by_label('New status').select_option(label=status)
            self.page.get_by_role('button', name='Save ticket').click(timeout=5000)
        except PlaywrightError as exc:
            # Playwright's TimeoutError is NOT the builtin TimeoutError. A click that
            # times out may still have reached the server, so report an unknown outcome
            # (the controller then verifies persisted state and never resubmits).
            raise OutcomeUnknown('UI submission outcome unknown') from exc
    def verify(self, ticket_id):
        # An independent GET from the allowed origin reads persisted application state;
        # a click event alone is not accepted as proof of success.
        self._path(ticket_id)
        response = self.page.request.get(self.base_url + self._path(ticket_id) + '/status', timeout=5000)
        if not response.ok: raise RuntimeError('Verification endpoint unavailable')
        data = response.json()
        if data.get('ticket_id') != ticket_id: raise RuntimeError('Ticket mismatch')
        return data['status']
