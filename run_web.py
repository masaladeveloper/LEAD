"""Start the locally hosted application and optionally open its browser tab."""
import argparse
import threading
import time
import urllib.request
import webbrowser

import uvicorn
from web_app import ROOT


def main():
    parser = argparse.ArgumentParser(description='Muneer Lead Workspace — local web app')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--host', default='127.0.0.1', help='Keep the default for PC-only use')
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    if not (ROOT / 'frontend' / 'dist' / 'index.html').is_file():
        parser.error('Interface not built. Run npm ci --prefix frontend then npm run build --prefix frontend.')
    if not args.no_browser:
        def open_when_ready():
            url = f'http://127.0.0.1:{args.port}'
            for _ in range(100):
                try:
                    with urllib.request.urlopen(url + '/api/health', timeout=1):
                        webbrowser.open(url)
                        return
                except OSError:
                    time.sleep(0.1)
        threading.Thread(target=open_when_ready, daemon=True).start()
    uvicorn.run('web_app:app', host=args.host, port=args.port, log_level='info')


if __name__ == '__main__':
    main()
