import pytest
import subprocess
import time
import socket
import os
import httpx
import websockets
import json
import asyncio

def get_free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

async def run_single_simulation(speed_ms, num_ticks, seed):
    port = get_free_port()
    python_exe = os.path.abspath(".venv/bin/python")
    
    env = os.environ.copy()
    env["SPEED_MS"] = str(speed_ms)
    env["NUM_TICKS"] = str(num_ticks)
    env["SEED"] = str(seed)
    # Ensure SandboxClient mock is used to prevent Rate Limit Errors
    env["GOOGLE_GENAI_USE_VERTEXAI"] = "FALSE"
    
    cmd = [python_exe, "-m", "uvicorn", "barkland.main:app", "--host", "127.0.0.1", "--port", str(port)]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    
    url = f"http://127.0.0.1:{port}"
    max_wait = 5
    start_time = time.time()
    while time.time() - start_time < max_wait:
        try:
             with socket.create_connection(('127.0.0.1', port), timeout=0.5):
                 break
        except OSError:
             await asyncio.sleep(0.1)
    else:
         process.terminate()
         stdout, stderr = process.communicate()
         raise RuntimeError(f"Server failed to start on port {port}. Err: {stderr.decode()}")
         
    ws_url = f"ws://127.0.0.1:{port}/ws"
    snapshots = []
    
    async with websockets.connect(ws_url) as ws:
        # Trigger simulation start AFTER connecting to WS
        async with httpx.AsyncClient() as client:
            await client.post(f"{url}/api/simulation/start")
            
        # Absorb initial frame
        while len(snapshots) < 15:
            try:
                message = await asyncio.wait_for(ws.recv(), timeout=2.0)
                data = json.loads(message)
                # Store comparable states (just dog details)
                snapshots.append({
                    "tick": data["tick"],
                    "dogs": [{ "name": d["name"], "state": d["state"], "needs": d["needs"] } for d in data["dogs"]]
                })
                if data["tick"] >= num_ticks - 10:
                    break
            except asyncio.TimeoutError:
                 break

    process.terminate()
    process.wait()
    return snapshots

@pytest.mark.asyncio
async def test_determinism_seed_matches():
    # Run Two Isolated Simulations with SAME seed
    run1 = await run_single_simulation(speed_ms=1, num_ticks=15, seed=42)
    run2 = await run_single_simulation(speed_ms=1, num_ticks=15, seed=42)

    assert len(run1) > 0
    assert len(run2) > 0
    
    # Compare state progressions
    min_len = min(len(run1), len(run2))
    for i in range(min_len):
         assert run1[i]["tick"] == run2[i]["tick"]
         assert run1[i]["dogs"] == run2[i]["dogs"], f"Divergence in tick {run1[i]['tick']}"
