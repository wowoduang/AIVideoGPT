from fastapi import FastAPI

from app.api.routes import workbench_state_router


def register_workbench_routes(app: FastAPI) -> None:
    app.include_router(workbench_state_router)
