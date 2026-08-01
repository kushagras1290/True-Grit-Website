import base64
import json
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

import websocket


ROOT = Path(__file__).resolve().parent
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
PORT = 9337

PALETTES = {
    "00-current": {},
    "01-sunbaked-olive": {
        "--palette-forest": "#4B5D3A",
        "--palette-forest-deep": "#303B28",
        "--palette-ivory": "#FBF3E6",
        "--palette-sage": "#E7DEC8",
        "--palette-terracotta": "#C66A3D",
        "--palette-terracotta-deep": "#A84F2A",
        "--palette-charcoal": "#2E3128",
        "--palette-grey-green": "#716F62",
        "--palette-gold": "#A87824",
    },
    "02-fresh-eucalyptus": {
        "--palette-forest": "#1F5A53",
        "--palette-forest-deep": "#153F3B",
        "--palette-ivory": "#F3F7F3",
        "--palette-sage": "#DCEAE3",
        "--palette-terracotta": "#C66F5B",
        "--palette-terracotta-deep": "#A95443",
        "--palette-charcoal": "#20312E",
        "--palette-grey-green": "#637672",
        "--palette-gold": "#967C32",
    },
    "03-ink-and-saffron": {
        "--palette-forest": "#304B50",
        "--palette-forest-deep": "#1B2D31",
        "--palette-ivory": "#F8F1E5",
        "--palette-sage": "#DCE4DE",
        "--palette-terracotta": "#C7782E",
        "--palette-terracotta-deep": "#A95D1E",
        "--palette-charcoal": "#272F30",
        "--palette-grey-green": "#687273",
        "--palette-gold": "#A97825",
    },
}


def cdp(ws, method, params=None):
    cdp.counter += 1
    request_id = cdp.counter
    ws.send(json.dumps({"id": request_id, "method": method, "params": params or {}}))
    while True:
        response = json.loads(ws.recv())
        if response.get("id") == request_id:
            if "error" in response:
                raise RuntimeError(response["error"])
            return response.get("result", {})


cdp.counter = 0


profile = Path(tempfile.mkdtemp(prefix="truegrit-colours-"))
process = subprocess.Popen(
    [
        str(CHROME),
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        "--remote-allow-origins=*",
        f"--remote-debugging-port={PORT}",
        f"--user-data-dir={profile}",
        "about:blank",
    ],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)

try:
    targets = None
    for _ in range(50):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list", timeout=1) as response:
                targets = json.loads(response.read())
            if targets:
                break
        except OSError:
            time.sleep(0.2)
    if not targets:
        raise RuntimeError("Chrome DevTools endpoint did not become ready")

    ws = websocket.create_connection(targets[0]["webSocketDebuggerUrl"], timeout=20)
    cdp(ws, "Page.enable")
    cdp(ws, "Runtime.enable")
    cdp(
        ws,
        "Emulation.setDeviceMetricsOverride",
        {"width": 1440, "height": 1000, "deviceScaleFactor": 1, "mobile": False},
    )
    cdp(ws, "Page.navigate", {"url": "http://127.0.0.1:5173/"})
    time.sleep(7)

    for name, palette in PALETTES.items():
        declarations = json.dumps(palette)
        expression = f"""
        (() => {{
          const values = {declarations};
          const root = document.documentElement;
          for (const [key, value] of Object.entries(values)) root.style.setProperty(key, value);
          root.style.setProperty('--color-border-subtle', `color-mix(in srgb, ${{values['--palette-forest'] || '#24483a'}} 14%, transparent)`);
          root.style.setProperty('--color-border-strong', `color-mix(in srgb, ${{values['--palette-forest'] || '#24483a'}} 32%, transparent)`);
          root.style.setProperty('--focus-ring', `0 0 0 3px color-mix(in srgb, ${{values['--palette-forest'] || '#24483a'}} 30%, transparent)`);
          window.scrollTo(0, 0);
          return document.title;
        }})()
        """
        cdp(ws, "Runtime.evaluate", {"expression": expression, "returnByValue": True})
        time.sleep(0.5)
        shot = cdp(ws, "Page.captureScreenshot", {"format": "png", "fromSurface": True})
        (ROOT / f"{name}.png").write_bytes(base64.b64decode(shot["data"]))

    ws.close()
finally:
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
    shutil.rmtree(profile, ignore_errors=True)
