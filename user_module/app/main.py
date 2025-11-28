from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from pathlib import Path

from .routers import files, auth, knowledge_base
from .routers.auth import get_current_user, SESSION_COOKIE_NAME

# Get the base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Create FastAPI app
app = FastAPI(
    title="User Module - File Management",
    description="Upload, process, and manage files with S3 storage",
    version="1.0.0"
)


# Auth middleware
class AuthMiddleware(BaseHTTPMiddleware):
    # Paths that don't require authentication
    PUBLIC_PATHS = {"/login", "/static", "/health"}

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Allow public paths
        if any(path.startswith(p) for p in self.PUBLIC_PATHS):
            return await call_next(request)

        # Check authentication
        user = get_current_user(request)
        if not user:
            # Redirect to login for HTML pages, return 401 for API
            if path.startswith("/api"):
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Not authenticated"}
                )
            return RedirectResponse(url="/login", status_code=302)

        # Add user to request state
        request.state.user = user
        return await call_next(request)


# Add auth middleware
app.add_middleware(AuthMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")

# Setup templates
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Include routers
app.include_router(auth.router)
app.include_router(files.router)
app.include_router(knowledge_base.router)


@app.get("/")
async def root(request: Request):
    """Render the main page"""
    user = getattr(request.state, 'user', None)
    return templates.TemplateResponse("index.html", {"request": request, "user": user})


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "user_module"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
