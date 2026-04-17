from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
import os
import asyncio
import subprocess
import shlex
import logging

from barkland.services.simulation_manager import sim, dog_agents, run_simulation, generate_unique_dog_names
from barkland.services.sandbox_manager import sandbox_clients, global_sandbox_client

logger = logging.getLogger(__name__)

router = APIRouter()

class ExecuteRequest(BaseModel):
    command: str

class ExecuteResponse(BaseModel):
    stdout: str
    stderr: str
    exit_code: int

@router.get("/", response_class=HTMLResponse)
async def get_dashboard():
    with open("barkland/templates/dashboard.html", "r") as f:
        content = f.read()
    return HTMLResponse(content=content)

@router.get("/api/dogs")
def get_dogs():
    return [dog.__dict__ for dog in sim.dogs.values()]

class StartSimulationRequest(BaseModel):
    count: int = Field(default=4, ge=1, le=200)

@router.post("/api/simulation/start")
async def start_simulation(req: StartSimulationRequest):
    if not sim.is_running:
        for dog_name in list(sandbox_clients.keys()):
            sandbox = sandbox_clients.pop(dog_name, None)
            if sandbox and not isinstance(sandbox, dict):
                asyncio.create_task(sandbox.terminate())
        
        sim.dogs.clear()
        dog_agents.clear()
        sim.tick_count = 0 
        
        names = generate_unique_dog_names(req.count)

        asyncio.create_task(run_simulation(names))
        return {"status": f"Simulation started with {req.count} dogs"}
    raise HTTPException(status_code=409, detail="Another simulation is already running right now. Please wait.")

@router.post("/api/simulation/stop")
async def stop_simulation():
    if sim.is_running:
        sim.is_running = False
        return {"status": "Simulation stop initiated"}
    return {"status": "Simulation was not running"}

@router.post("/api/simulation/reset_warmpool")
async def reset_warmpool():
    if sim.is_running:
        raise HTTPException(status_code=400, detail="Cannot reset warmpool while simulation is running")
        
    try:
        subprocess.run(["kubectl", "delete", "sandboxclaims", "--all", "-n", "barkland"], check=True, capture_output=True)
        
        subprocess.run(["kubectl", "delete", "sandboxwarmpool", "dog-agent-warmpool", "-n", "barkland", "--ignore-not-found=true"], check=True, capture_output=True)
        
        with open("k8s/sandbox_warmpool.yaml", "r") as f:
            template = f.read()
        
        namespace = os.getenv("NAMESPACE", "barkland")
        replicas = os.getenv("WARMPOOL_REPLICAS", "200")
        
        manifest = template.replace("${NAMESPACE}", namespace).replace("${WARMPOOL_REPLICAS}", replicas)
        
        subprocess.run(["kubectl", "apply", "-f", "-"], input=manifest.encode(), check=True, capture_output=True)
        
        target = int(replicas)
        ready = "0"
        for _ in range(12): # 12 * 5 = 60 seconds
            result = subprocess.run(["kubectl", "get", "sandboxwarmpool", "dog-agent-warmpool", "-n", "barkland", "-o", "jsonpath={.status.readyReplicas}"], capture_output=True, text=True)
            ready = result.stdout.strip() or "0"
            if ready == str(target):
                return {"status": f"Warmpool reset complete. All {target} pods are ready."}
            await asyncio.sleep(5)
            
        return {"status": f"Warmpool reset initiated. Timed out waiting for full replenishment. Current ready: {ready}/{target}"}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset warmpool: {e}")

@router.post("/execute", response_model=ExecuteResponse)
async def execute_command(request: ExecuteRequest):
    try:
        args = shlex.split(request.command)
        process = subprocess.run(
            args,
            capture_output=True,
            text=True,
            cwd="/app"
        )
        return ExecuteResponse(
            stdout=process.stdout,
            stderr=process.stderr,
            exit_code=process.returncode
        )
    except Exception as e:
        return ExecuteResponse(
            stdout="",
            stderr=f"Failed to execute command: {str(e)}",
            exit_code=1
        )
