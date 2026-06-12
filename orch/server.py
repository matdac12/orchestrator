import json
import sys
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

from orch import db
from orch.dashboard import PAGE


def render_api_state(project):
    conn = db.connect()
    try:
        state = db.get_state(conn, project)
        return json.dumps(state), "application/json; charset=utf-8"
    except db.NotFound as e:
        return json.dumps({"error": str(e)}), "application/json; charset=utf-8"
    finally:
        conn.close()


def render_index(project):
    return PAGE.format(project=project), "text/html; charset=utf-8"


def make_handler(default_project):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, body, ctype, code=200):
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            project = qs.get("project", [default_project])[0]
            if parsed.path == "/api/state":
                body, ctype = render_api_state(project)
                self._send(body, ctype)
            elif parsed.path == "/":
                body, ctype = render_index(project)
                self._send(body, ctype)
            else:
                self._send("not found", "text/plain; charset=utf-8", 404)

        def log_message(self, *args):
            pass  # quiet

    return Handler


def serve(project, port=8787):
    try:
        httpd = HTTPServer(("127.0.0.1", port), make_handler(project))
    except OSError as e:
        print(f"orch serve: cannot bind 127.0.0.1:{port}: {e}",
              file=sys.stderr)
        raise
    print(f"orch dashboard: http://127.0.0.1:{port}/  (project: {project})")
    print("Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
    except Exception:
        # Never die silently: surface the traceback so a dead dashboard is
        # diagnosable even when launched in the background.
        print("orch serve: server crashed:", file=sys.stderr)
        traceback.print_exc()
        raise
    finally:
        httpd.server_close()
