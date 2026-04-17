import pytest
import subprocess
import time
import socket
import os

def get_free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

@pytest.fixture(scope="function")
def live_server_url():
    port = get_free_port()
    import sys
    python_exe = sys.executable
    
    env = os.environ.copy()
    env["SPEED_MS"] = "1" # Fast mode ticks
    env["NUM_TICKS"] = "100"
    
    # Start uvicorn
    cmd = [python_exe, "-m", "uvicorn", "barkland.main:app", "--host", "127.0.0.1", "--port", str(port)]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    
    url = f"http://127.0.0.1:{port}"
    max_wait = 5
    start_time = time.time()
    while time.time() - start_time < max_wait:
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=1):
                break
        except OSError:
            time.sleep(0.1)
    else:
        process.terminate()
        stdout, stderr = process.communicate()
        raise RuntimeError(f"Server failed to start on port {port}. Err: {stderr.decode()}")
        
    yield url
    
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
