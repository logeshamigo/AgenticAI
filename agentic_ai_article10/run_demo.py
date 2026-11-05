"""Run a local fictional browser workflow; no LLM API key required."""
import argparse
from pathlib import Path
from threading import Thread
from playwright.sync_api import sync_playwright
from agent import Task, Checkpoints, Controller
from browser_adapter import PlaywrightAdapter
from local_app import TicketServer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--approve', action='store_true', help='Explicitly authorize the local ticket update')
    parser.add_argument('--headed', action='store_true', help='Show the browser window')
    parser.add_argument('--checkpoint', default='run_state.json')
    args = parser.parse_args()
    server = TicketServer()
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not args.headed)
            try:
                context = browser.new_context(service_workers='block')
                page = context.new_page()
                origin = f'http://127.0.0.1:{server.server_port}'
                # Never forward this demo browser to an unapproved remote site.
                def route(request_route):
                    if request_route.request.url.startswith(origin + '/'):
                        request_route.continue_()
                    else:
                        request_route.abort()
                context.route('**/*', route)
                adapter = PlaywrightAdapter(page, origin)
                result = Controller(adapter, Checkpoints(Path(args.checkpoint))).run(Task('T-104', 'Resolved', approved=args.approve))
                print('Controller result:', result)
                print('Persisted ticket status:', adapter.verify('T-104'))
                print('Number of writes:', page.request.get(origin + '/ticket/T-104/status').json()['writes'])
            finally: browser.close()
    finally:
        server.shutdown()
        server.server_close()

if __name__ == '__main__': main()
