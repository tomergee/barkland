from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
import random
import warnings
from contextlib import asynccontextmanager

try:
    from dotenv import load_dotenv
    load_dotenv('.configuration', override=True)
except ImportError:
    pass

# Seed early
random.seed(int(os.getenv("SEED", "42")))

warnings.filterwarnings("ignore", message=".*Your application has authenticated using end user credentials.*")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="websockets.legacy.server")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    from k8s_agent_sandbox.client import AsyncSandboxClient
    from k8s_agent_sandbox.models import SandboxDirectConnectionConfig
except ImportError:
    AsyncSandboxClient = None
    SandboxDirectConnectionConfig = None

from barkland.api.endpoints import router as api_router
from barkland.api.websocket import router as ws_router
from barkland.services.sandbox_manager import set_global_sandbox_client

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    is_local = os.getenv("ENVIRONMENT", "").lower() == "local"
    if not is_local and AsyncSandboxClient and SandboxDirectConnectionConfig:
        router_url = os.getenv("SANDBOX_ROUTER_URL", "http://sandbox-router-svc:8000")
        connection_config = SandboxDirectConnectionConfig(api_url=router_url, server_port=8000)
        client = AsyncSandboxClient(connection_config=connection_config)
        set_global_sandbox_client(client)
        logger.info("Sandbox client initialized")
    else:
        logger.info("Running in local mode or missing SDK, sandbox client not initialized")
        
    yield
    
    # Shutdown
    from barkland.services.sandbox_manager import global_sandbox_client
    if global_sandbox_client:
        await global_sandbox_client.close()
        logger.info("Sandbox client closed")

app = FastAPI(lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(ws_router)
