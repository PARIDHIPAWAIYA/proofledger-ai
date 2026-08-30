from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from proofledger import __version__
from proofledger.api import WorkspaceDependency, router
from proofledger.config import get_settings

settings = get_settings()

app = FastAPI(
    title="ProofLedger AI",
    description="Object-centric, uncertainty-aware financial close controller",
    version=__version__,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/health")
def health(workspace: WorkspaceDependency) -> dict[str, str]:
    repository = workspace.repository
    return {
        "status": "ok",
        "version": __version__,
        "storage": "database" if repository else "memory",
        "database": "ok" if repository and repository.health() else "not_configured",
    }
