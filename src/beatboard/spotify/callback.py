"""OAuth callback HTTP server for Spotify Authorization Code flow."""

from __future__ import annotations

import html as html_lib
import http.server
import queue
import socketserver
import threading
import time
import urllib.parse

from ..logs import log


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler that captures Spotify OAuth callback."""

    _STYLE = """
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:radial-gradient(900px 500px at 50% -10%, #1e2a4a 0%, #0a0a12 55%, #050508 100%);color:#e8e8ef;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Inter,Helvetica,Arial,sans-serif;padding:24px}
.card{width:100%;max-width:480px;background:rgba(24,24,33,.92);backdrop-filter:blur(12px);border:1px solid rgba(255,255,255,.08);border-radius:24px;padding:40px 32px;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,.6),0 1px 0 rgba(255,255,255,.06) inset}
.logo{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:#6b7cff;font-weight:700;margin-bottom:22px}
.icon{width:72px;height:72px;border-radius:50%;display:flex;align-items:center;justify-content:center;margin:0 auto 20px;font-size:34px}
.icon.success{background:linear-gradient(135deg,#1DB954,#1ed760);color:#fff;box-shadow:0 8px 24px rgba(29,185,84,.4)}
.icon.error{background:linear-gradient(135deg,#ff4d6d,#ff3b30);color:#fff;box-shadow:0 8px 24px rgba(255,59,48,.35)}
.icon.warn{background:linear-gradient(135deg,#ffb020,#ff8c00);color:#fff;box-shadow:0 8px 24px rgba(255,176,32,.3)}
h1{font-size:24px;font-weight:700;margin:0 0 10px;letter-spacing:-.02em}
p{color:#a8a8b8;line-height:1.6;margin:0 0 16px;font-size:15px}
.hint{font-size:13px;color:#7a7a8a}
.btn{margin-top:18px;appearance:none;border:0;background:#fff;color:#0a0a12;font-weight:600;padding:10px 22px;border-radius:999px;cursor:pointer;font-size:14px}
.btn:hover{background:#f0f0f0}
.btn-secondary{background:rgba(255,255,255,.08);color:#e8e8ef;border:1px solid rgba(255,255,255,.12)}
.btn-secondary:hover{background:rgba(255,255,255,.14)}
.footer{margin-top:26px;font-size:11px;color:#5a5a6a;letter-spacing:.04em}
code{background:rgba(255,255,255,.08);padding:2px 6px;border-radius:6px;font-size:12px;color:#e8e8ef;word-break:break-all}
"""

    def _html(self, *, icon: str, title: str, body: str, footer: str = "") -> bytes:
        doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>BeatBoard — {html_lib.escape(title)}</title>
<style>{self._STYLE}</style>
</head>
<body>
  <div class="card">
    <div class="logo">♫ BeatBoard</div>
    <div class="icon {icon}">{"✓" if icon == "success" else "✕" if icon == "error" else "!"}</div>
    <h1>{html_lib.escape(title)}</h1>
    {body}
    {footer}
  </div>
</body>
</html>"""
        return doc.encode()

    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        if parsed.path.endswith("/callback"):
            code = qs.get("code", [None])[0]
            state = qs.get("state", [None])[0]
            error = qs.get("error", [None])[0]
            self.server.auth_code = code  # type: ignore[attr-defined]
            self.server.auth_state = state  # type: ignore[attr-defined]
            self.server.auth_error = error  # type: ignore[attr-defined]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if error:
                safe = html_lib.escape(error)
                body = f'<p>Spotify returned an error and BeatBoard could not connect.</p><p><code>{safe}</code></p><p class="hint">Close this window and run <code>beatboard --api</code> again to retry. Check your app redirect URI is <code>http://127.0.0.1:8888/callback</code>.</p><button class="btn btn-secondary" onclick="window.close()">Close window</button>'
                self.wfile.write(
                    self._html(
                        icon="error",
                        title="Authentication failed",
                        body=body,
                        footer='<div class="footer">Need help? See Spotify Dashboard → Edit Settings</div>',
                    )
                )
            elif code:
                body = """<p>Your Spotify account is now connected. BeatBoard will stream track changes via WebSocket — no polling.</p><p class="hint">You can close this window and return to the terminal. It will try to close automatically in <span id="cd">4</span>s.</p><button class="btn" onclick="window.close()">Close window</button><script>let n=4,el=document.getElementById('cd');const t=setInterval(()=>{n--;if(el)el.textContent=n;if(n<=0){clearInterval(t);try{window.close()}catch(e){}}},1000)</script>"""
                self.wfile.write(
                    self._html(
                        icon="success",
                        title="Authentication successful!",
                        body=body,
                        footer='<div class="footer">Listening via wss://dealer.spotify.com • BeatBoard</div>',
                    )
                )
            else:
                body = '<p>No authorization code was received. The redirect may have been blocked.</p><p class="hint">Close this window and run <code>beatboard --api</code> again. Allow the browser to open <code>http://127.0.0.1:8888/callback</code>.</p><button class="btn btn-secondary" onclick="window.close()">Close window</button>'
                self.wfile.write(
                    self._html(
                        icon="warn",
                        title="No code received",
                        body=body,
                    )
                )
            try:
                self.server.code_queue.put((code, state, error), block=False)  # type: ignore[attr-defined]
            except queue.Full:
                pass
        else:
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                self._html(
                    icon="error",
                    title="Not found",
                    body='<p class="hint">Unknown path. Expected <code>/callback?code=...</code></p>',
                )
            )

    def log_message(self, format, *args):  # noqa: A002
        return


def _run_local_server(
    host: str = "127.0.0.1", port: int = 8888, timeout: int = 180
) -> tuple[str | None, str | None, str | None]:
    """Run a temporary HTTP server to capture OAuth callback."""
    code_queue: queue.Queue = queue.Queue()
    t0 = time.perf_counter()
    log(
        "api",
        f"[cyan]api[/cyan] [dim]·[/dim] callback listening on [cyan]http://{host}:{port}/callback[/cyan] [dim]·[/dim] [cyan]{timeout}s[/cyan]",
    )

    class ReusableTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

    with ReusableTCPServer((host, port), _CallbackHandler) as httpd:
        httpd.code_queue = code_queue  # type: ignore[attr-defined]
        httpd.auth_code = None  # type: ignore[attr-defined]
        httpd.auth_state = None  # type: ignore[attr-defined]
        httpd.auth_error = None  # type: ignore[attr-defined]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            code, state, error = code_queue.get(timeout=timeout)
            dt = (time.perf_counter() - t0) * 1000
            log(
                "api",
                f"[cyan]api[/cyan] [dim]·[/dim] callback {'[green]ok[/green]' if code else '[red]error[/red]'} [dim]·[/dim] [cyan]{dt:.0f}ms[/cyan]"
                + (f" [dim]({error})[/dim]" if error else ""),
            )
            return code, state, error
        except queue.Empty:
            dt = (time.perf_counter() - t0) * 1000
            log(
                "api",
                f"[yellow]api[/yellow] [dim]·[/dim] callback timeout [dim]·[/dim] [yellow]{dt:.0f}ms[/yellow]",
            )
            return None, None, "timeout"
        finally:
            httpd.shutdown()
            thread.join(timeout=2)
