import pytest
import httpx
import websockets
import json
import asyncio

@pytest.mark.asyncio
async def test_simulation_sleep_ratio(live_server_url):
    # 1. Trigger simulation start
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{live_server_url}/api/simulation/start")
        assert response.status_code == 200
        assert "Simulation started" in response.json()["status"]

    ws_url = live_server_url.replace("http", "ws") + "/ws"
    
    sleep_count = 0
    total_samples = 0
    ticks_seen = 0
    max_ticks = 100 # From conftest.py env
    
    async with websockets.connect(ws_url) as ws:
        while ticks_seen < max_ticks - 10:
            try:
                message = await asyncio.wait_for(ws.recv(), timeout=2.0)
                data = json.loads(message)
                
                ticks_seen = data["tick"]
                for dog in data["dogs"]:
                    total_samples += 1
                    if dog["state"] == "sleeping":
                        sleep_count += 1
                
                if ticks_seen >= max_ticks - 15:
                    break
            except asyncio.TimeoutError:
                 break

    assert total_samples > 0
    sleep_percent = (sleep_count / total_samples) * 100
    print(f"\n--- Sleep Ratio: {sleep_percent:.2f}% ({sleep_count}/{total_samples})")
    
    # Assert broadly to be safe against random walks
    assert 30 <= sleep_percent <= 80, f"Sleep ratio {sleep_percent}% out of bounds"
