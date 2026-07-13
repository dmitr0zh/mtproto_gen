from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import subprocess
import config
import subprocess
import binascii
import os
import time

# CONFIG
ADMIN_USER = config.user
ADMIN_PASSWORD = config.psw

# --- Настройки сервера ---
PREFIX = "ee"
DOMAIN = "80.85.241.26"
PORT = "443"

#Домен для обфускации и его перевод в HEX
def get_postfix_from_system() -> str: 
    try:
        result = subprocess.run(["mtproxymax", "domain", "get"], capture_output=True, text=True, check=True) #Запрос домена в MTPROXYMAX
        return binascii.hexlify(result.stdout.strip().encode('utf-8')).decode('utf-8')
    except Exception:
        return None

def get_user_secret(username: str) -> str:
    #Ищет в файле и возвращает чистый 32-значный секрет
    file_path = "/opt/mtproxymax/secrets.conf"
    if not os.path.exists(file_path):
        return ""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("#") or not line.strip():
                    continue
                parts = line.strip().split("|")
                if parts.lower() == username.lower():
                    return parts # Возвращаем только 32 символа из базы
    except Exception:
        pass
    return ""

# БЛОК КОДА
TARGET_USER = "ONE"
raw_secret = get_user_secret(TARGET_USER)
 
# Собираем полный секрет для Telegram (ee + 32 символа + hex домена)
if raw_secret:
    SECRET_KEY_TG = PREFIX + raw_secret + get_postfix_from_system()
else:
    SECRET_KEY_TG = None

# APP
app = FastAPI()

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY_TG
)

templates = Jinja2Templates(directory="templates")

# AUTH
def require_auth(request: Request):
    if not request.session.get("auth"):
        return RedirectResponse("/login", status_code=303)

# MTProxyMax
def load_users():
    users = []
    file_path = "/opt/mtproxymax/secrets.conf"
    with open(file_path, "r") as f:

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
                "link": f"tg://proxy?server={DOMAIN}&port={PORT}&secret={PREFIX}{secret}{get_postfix_from_system()}"
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

#Limits
@app.post("/limit/{name}")
def limit(
    request: Request, 
    name: str, 
    ips: int = Form(...), 
    conn: int = Form(...)
):
    if redirect := require_auth(request):
        return redirect
    cmd_ips = f'echo "yes" | mtproxymax secret setlimit {name} ips {ips}'
    cmd_conn = f'echo "yes" | mtproxymax secret setlimit {name} conns {conn}'
    
    # Запускаем в реальном shell и выводим логи в терминал сервера для дебага
    print(f"--- Установка лимитов для {name} ---")
    res_ips = subprocess.run(cmd_ips, shell=True, capture_output=True, text=True)
    print(f"Ответ mtproxy (IPS): {res_ips.stdout.strip()} {res_ips.stderr.strip()}")
    
    res_conn = subprocess.run(cmd_conn, shell=True, capture_output=True, text=True)
    print(f"Ответ mtproxy (CONN): {res_conn.stdout.strip()} {res_conn.stderr.strip()}")
    print("-----------------------------------")
    
    # Делаем редирект, чтобы страница обновилась
    return RedirectResponse("/", status_code=303)