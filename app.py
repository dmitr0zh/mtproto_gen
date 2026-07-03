from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

import subprocess
import config

# CONFIG
ADMIN_USER = config.user
ADMIN_PASSWORD = config.psw

DOMAIN = "zubmp.hopto.org"
PORT = "443"

SECRET_KEY = "ee808b414bea0425b3d46c6dcc40a8d152646f636b65722e636f6d"

SECRETS_FILE = "/opt/mtproxymax/secrets.conf"

# APP
app = FastAPI()

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY
)

templates = Jinja2Templates(directory="templates")

# AUTH
def require_auth(request: Request):
    if not request.session.get("auth"):
        return RedirectResponse("/login", status_code=303)

# MTProxyMax
def load_users():
    users = []

    with open(SECRETS_FILE, "r") as f:

        for line in f:

            if line.startswith("#"):
                continue

            line = line.strip()

            if not line:
                continue

            parts = line.split("|")

            if len(parts) < 9:
                continue

            label = parts[0]
            secret = parts[1]
            enabled = parts[3]
            max_conn = parts[4]
            max_ips = parts[5]

            users.append({
                "name": label,
                "secret": secret,
                "active": enabled == "true",
                "max_conn": max_conn,
                "max_ips": max_ips,
                "link": f"tg://proxy?server={DOMAIN}&port={PORT}&secret=ee{secret}646f636b65722e636f6d"
            })

    return users


def run_cmd(cmd):
    subprocess.run(
        cmd,
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

# LOGIN
@app.get("/login")
def login_page(request: Request):

    return templates.TemplateResponse(
        request,
        "login.html",
        {}
    )


@app.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):

    if username == ADMIN_USER and password == ADMIN_PASSWORD:

        request.session["auth"] = True

        return RedirectResponse("/", status_code=303)

    return RedirectResponse("/login", status_code=303)


@app.get("/logout")
def logout(request: Request):

    request.session.clear()

    return RedirectResponse("/login", status_code=303)

# INDEX
@app.get("/")
def index(request: Request):

    if redirect := require_auth(request):
        return redirect

    users = load_users()

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "users": users
        }
    )

# CREATE
@app.post("/create")
def create(
    request: Request,
    name: str = Form(...)
):

    if redirect := require_auth(request):
        return redirect

    run_cmd(f"mtproxymax secret add {name}")

    return RedirectResponse("/", status_code=303)

# DISABLE
@app.get("/disable/{name}")
def disable(request: Request, name: str):

    if redirect := require_auth(request):
        return redirect

    run_cmd(f"mtproxymax secret disable {name}")

    return RedirectResponse("/", status_code=303)


# ENABLE
@app.get("/enable/{name}")
def enable(request: Request, name: str):

    if redirect := require_auth(request):
        return redirect

    run_cmd(f"mtproxymax secret enable {name}")

    return RedirectResponse("/", status_code=303)

# DELETE
@app.get("/delete/{name}")
def delete(request: Request, name: str):

    if redirect := require_auth(request):
        return redirect

    run_cmd(
        f'printf "yes\n" | mtproxymax secret remove {name}'
    )

    return RedirectResponse("/", status_code=303)