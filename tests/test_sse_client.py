import httpx

pv = "SPEAR:BeamCurrAvg"
url = f"http://localhost:8001/sse?pv={pv}"

with httpx.stream("GET", url, timeout=None) as r:
    r.raise_for_status()
    for line in r.iter_lines():
        if not line:
            continue
        print(line)
