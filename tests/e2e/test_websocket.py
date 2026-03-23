import pytest
import websockets
import json
import asyncio

@pytest.mark.asyncio
async def test_websocket_snapshot_format(live_server_url):
    ws_url = live_server_url.replace("http", "ws") + "/ws"
    
    async with websockets.connect(ws_url) as ws:
        # Receive first snapshot (broadcasted on connection)
        try:
            message = await asyncio.wait_for(ws.recv(), timeout=2.0)
            data = json.loads(message)
            
            # Assert schema
            assert "tick" in data
            assert "dogs" in data
            assert "sandboxes" in data
            
            assert isinstance(data["tick"], int)
            assert isinstance(data["dogs"], list)
            assert isinstance(data["sandboxes"], list)
            
            if data["dogs"]:
                dog = data["dogs"][0]
                assert "name" in dog
                assert "state" in dog
                assert "needs" in dog
                assert "latest_bark" in dog
                assert "personality" in dog

        except asyncio.TimeoutError:
             pytest.fail("WebSocket timed out waiting for initial frame")
