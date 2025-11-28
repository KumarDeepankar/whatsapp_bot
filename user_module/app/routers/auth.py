from fastapi import APIRouter, Request, Response, HTTPException, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from ..services.auth_service import get_auth_service

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="templates")

SESSION_COOKIE_NAME = "session_token"


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Render login page"""
    # Check if already logged in
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        auth_service = get_auth_service()
        if auth_service.validate_session(token):
            return RedirectResponse(url="/", status_code=302)

    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": None
    })


@router.post("/login")
async def login(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...)
):
    """Handle login form submission"""
    auth_service = get_auth_service()

    if auth_service.verify_credentials(username, password):
        # Create session
        token = auth_service.create_session(username)

        # Redirect to home with session cookie
        redirect_response = RedirectResponse(url="/", status_code=302)
        redirect_response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=token,
            httponly=True,
            max_age=86400,  # 24 hours
            samesite="lax"
        )
        return redirect_response
    else:
        # Return login page with error
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid username or password"
        }, status_code=401)


@router.get("/logout")
async def logout(request: Request):
    """Handle logout"""
    token = request.cookies.get(SESSION_COOKIE_NAME)

    if token:
        auth_service = get_auth_service()
        auth_service.destroy_session(token)

    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response


def get_current_user(request: Request) -> str:
    """Get current logged in user from session"""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None

    auth_service = get_auth_service()
    return auth_service.validate_session(token)


def require_auth(request: Request):
    """Check if user is authenticated, redirect to login if not"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
