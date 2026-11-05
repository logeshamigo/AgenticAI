import json
import threading
import unittest
from urllib.request import urlopen, Request
from urllib.parse import urlencode
from local_app import TicketServer

class TestLocalApp(unittest.TestCase):
    def setUp(self):
        self.server = TicketServer()
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.origin = f'http://127.0.0.1:{self.server.server_port}'
    def test_initial_state_and_ui(self):
        html = urlopen(self.origin+'/ticket/T-104').read().decode()
        self.assertIn('data-testid="ticket-status"',html)
        self.assertIn('UNTRUSTED TEST TEXT',html)
        state = json.load(urlopen(self.origin+'/ticket/T-104/status'))
        self.assertEqual((state['status'], state['writes']),('Open',0))
    def test_post_commits_once_and_endpoint_verifies(self):
        payload=urlencode({'status':'Resolved'}).encode()
        urlopen(Request(self.origin+'/ticket/T-104',data=payload,method='POST'))
        state=json.load(urlopen(self.origin+'/ticket/T-104/status'))
        self.assertEqual((state['status'],state['writes']),('Resolved',1))

if __name__=='__main__': unittest.main()
