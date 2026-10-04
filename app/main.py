from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import bcrypt
from contextlib import asynccontextmanager
import sqlite3
from connect import init_db
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
import random
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pydantic_settings import BaseSettings
import html
import secrets
from urllib.parse import urlparse
import math
from datetime import datetime, timedelta, timezone
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(lifespan=lifespan)
 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "https://localhost:8000", "https://leukelootjes.nl"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    ENCRYPTION_KEY: str = ""

    SECRET_KEY: str = ""
    SMTP_HOST: str = ""
    SMTP_PORT: int = 2525
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SENDER_EMAIL: str = ""

    BASE_URL: str = "http://localhost:8000"

    MAX_ATTEMPTS: int = 6
    LOCKOUT_MINUTES: int = 15

    NAMES: list[str] = []
    EXCLUSIONS: dict[str, list[str]] = {}

    @field_validator("BASE_URL")
    @classmethod
    def strip_slash(cls, v: str) -> str:
        return v.rstrip("/")

settings = Settings()

from cryptography.fernet import Fernet, InvalidToken

fernet = Fernet(settings.ENCRYPTION_KEY)

def encrypt(value: str) -> str:
    return fernet.encrypt(value.encode("utf-8")).decode("utf-8")

def decrypt(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return fernet.decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return None

app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def hash_token(token: str) -> str:
    return bcrypt.hashpw(token.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def create_message(sender_id: int, recipient_name: str,
                   recipient_email: str, body: str) -> str:
    secret = secrets.token_urlsafe(32)
    token_hash = hash_token(secret)
    execute_sql("INSERT INTO messages (token_hash, sender_id, recipient_name, recipient_email, body) "
        "VALUES (?, ?, ?, ?, ?)", (token_hash, sender_id, recipient_name, recipient_email, body),)
    rows = execute_sql("SELECT id FROM messages WHERE token_hash = ?;", (token_hash,))
    return f"{rows[0][0]}.{secret}"

def get_open_message(token: str):
    message_id, _, secret = token.partition(".")
    if not message_id.isdigit() or len(message_id) > 10 or len(secret) != 43:
        raise HTTPException(status_code=404)
    rows = execute_sql(
        "SELECT id, token_hash, sender_id, recipient_name, body "
        "FROM messages WHERE id = ? AND replied_at IS NULL;",
        (int(message_id),),
    )
    if not rows or not bcrypt.checkpw(secret.encode("utf-8"), rows[0][1].encode("utf-8")):
        raise HTTPException(status_code=404)
    return rows[0]

def send_email(recipient: str, subject: str, text_body: str, html_body: str) -> bool:
    msg = MIMEMultipart("alternative")
    msg["From"] = settings.SENDER_EMAIL
    msg["To"] = recipient
    msg["Subject"] = subject

    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SENDER_EMAIL, [recipient], msg.as_string())
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False


def build_email(name: str, message: str, reply_url: str | None = None) -> tuple[str, str]:
    safe_name = html.escape(name)
    safe_message = html.escape(message)

    text = f"Hallo {name}!\n\nSinterklaas heeft een vraag voor je:\n\n{message}\n\nLet op: niet op deze e-mail reageren, die wordt dan namelijk doorgestuurd naar Leon, en niet naar de persoon die dit bericht heeft gestuurd."

    reply_button = ""
    if reply_url:
        text += f"\n\nReageer op dit anonieme bericht: {reply_url}"
        reply_button = f"""
                <a href="{reply_url}"
                   style="display:inline-block; margin-top:24px; padding:12px 24px; background-color:#4f6bed;
                          color:#ffffff; text-decoration:none; border-radius:6px; font-size:16px;">
                  Reageer
                </a>"""

    html_body = f"""\
<!DOCTYPE html>
<html>
  <body style="margin:0; padding:0; background-color:#f4f4f7; font-family:Arial, Helvetica, sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f7; padding:24px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="600" cellpadding="0" cellspacing="0"
                 style="background-color:#ffffff; border-radius:8px; padding:32px; max-width:600px;">
            <tr>
              <td>
                <h1 style="margin:0 0 16px; color:#222; font-size:24px;">Hallo {safe_name}!</h1>
                <p style="margin:0 0 16px; color:#555; font-size:16px; line-height:1.5;">
                  Sinterklaas wil je iets vragen:
                </p>
                <div style="background-color:#f0f4ff; border-left:4px solid #4f6bed; padding:16px;
                            color:#222; font-size:16px; line-height:1.5; white-space:pre-wrap;">{safe_message}</div>{reply_button}<br>
                <p style="margin:8px 0 8px; color:#555; font-size:16px;">Let op: niet op deze e-mail reageren, die wordt dan namelijk doorgestuurd naar Leon, en niet naar de persoon die dit bericht heeft gestuurd.</p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""
    return text, html_body

def build_reply_email(recipient_name: str, original: str, reply: str) -> tuple[str, str]:
    safe_name = html.escape(recipient_name)
    safe_original = html.escape(original)
    safe_reply = html.escape(reply)

    text = (f"{recipient_name} heeft gereageerd op je anonieme bericht!\n\n"
            f"Jouw bericht:\n{original}\n\nReactie van {recipient_name}:\n{reply}\n\nAls je meer wil vragen, stuur een nieuw bericht op https://leukelootjes.nl/berichten\n\nLet op: niet op deze e-mail reageren, die wordt dan namelijk doorgestuurd naar Leon, en niet naar de persoon die dit bericht heeft gestuurd.")

    html_body = f"""\
<!DOCTYPE html>
<html>
  <body style="margin:0; padding:0; background-color:#f4f4f7; font-family:Arial, Helvetica, sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f7; padding:24px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="600" cellpadding="0" cellspacing="0"
                 style="background-color:#ffffff; border-radius:8px; padding:32px; max-width:600px;">
            <tr>
              <td>
                <h1 style="margin:0 0 16px; color:#222; font-size:24px;">{safe_name} heeft gereageerd!</h1>
                <p style="margin:0 0 8px; color:#777; font-size:14px;">Jouw bericht:</p>
                <div style="border-left:4px solid #cccccc; padding:8px 16px; margin:0 0 24px;
                            color:#777; font-size:14px; line-height:1.5; white-space:pre-wrap;">{safe_original}</div>
                <p style="margin:0 0 8px; color:#555; font-size:16px;">Reactie van {safe_name}:</p>
                <div style="background-color:#f0f4ff; border-left:4px solid #4f6bed; padding:16px;
                            color:#222; font-size:16px; line-height:1.5; white-space:pre-wrap;">{safe_reply}</div><br>
                <p style="margin:0 0 8px; color:#555; font-size:16px;">Als je meer wil vragen, stuur een nieuw bericht op <a href="https://leukelootjes.nl/berichten">https://leukelootjes.nl/berichten</a></p>
                <p style="margin:8px 0 8px; color:#555; font-size:16px;">Let op: niet op deze e-mail reageren, die wordt dan namelijk doorgestuurd naar Leon, en niet naar de persoon die dit bericht heeft gestuurd.</p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""
    return text, html_body

def execute_sql(sql, params=()):
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
        row = cursor.fetchall()
        return row
        
def get_user(username: str):
    rows = execute_sql(
        "SELECT user_id, username, hashed_password FROM users WHERE username = ?;", (username,),
    )
    if rows:
        return rows[0]
    else:
        return None
    
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    user = request.session.get("username")
    return templates.TemplateResponse(
        request=request, name="404.html", status_code=404, context={"logged_in_user":user}
    )

@app.post("/auth/username")
async def username_step(request: Request, username: str = Form()):
    username = username.strip().lower()
    request.session.clear()
    request.session["pending_username"] = username
    if username not in settings.NAMES:
        return templates.TemplateResponse(request=request, name="error.html", status_code=400, context={"error":f"{username.capitalize()} doet niet mee met Sinterklaas dit jaar."})
    if get_user(username):
        return RedirectResponse("/auth/login", status_code=303)
    else:
        return RedirectResponse("/auth/register", status_code=303)

@app.get("/auth/login")
async def login_form(request: Request):
    if not request.session.get("pending_username"):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "login.html",
        {"username": request.session["pending_username"]})

@app.post("/auth/login")
async def login(request: Request, password: str = Form()):
    username = request.session.get("pending_username")
    if not username:
        return RedirectResponse("/", status_code=303)

    rows = execute_sql(
        "SELECT hashed_password, failed_attempts, locked_until FROM users WHERE username = ?;",
        (username,),
    )
    if not rows:
        return templates.TemplateResponse(
            request=request, name="error.html", status_code=400,
            context={"error": "Onbekend account."}
        )
    hashed, failed, locked_until = rows[0]
    now = datetime.now(timezone.utc)

    if locked_until:
        until = datetime.fromisoformat(locked_until)
        if until > now:
            minutes = math.ceil((until - now).total_seconds() / 60)
            return templates.TemplateResponse(
                request=request, name="error.html", status_code=429,
                context={"error": f"Te veel mislukte pogingen. Probeer het over {minutes} minuten opnieuw."}
            )

    if not bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8")):
        failed = (failed or 0) + 1
        if failed >= settings.MAX_ATTEMPTS:
            until = (now + timedelta(minutes=settings.LOCKOUT_MINUTES)).isoformat()
            execute_sql(
                "UPDATE users SET failed_attempts = 0, locked_until = ? WHERE username = ?;",
                (until, username),
            )
            return templates.TemplateResponse(
                request=request, name="error.html", status_code=429,
                context={"error": f"Te veel mislukte pogingen. Je account is {settings.LOCKOUT_MINUTES} minuten geblokkeerd."}
            )
        execute_sql("UPDATE users SET failed_attempts = ? WHERE username = ?;", (failed, username))
        return templates.TemplateResponse(
            request=request, name="error.html", status_code=400,
            context={"error": f"Onjuist wachtwoord. Nog {settings.MAX_ATTEMPTS - failed} pogingen over."}
        )

    execute_sql(
        "UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE username = ?;",
        (username,),
    )
    request.session["username"] = username
    return RedirectResponse(url="/", status_code=303)

@app.get("/auth/register")
async def register_form(request: Request):
    if not request.session.get("pending_username"):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(request, "register.html",
        {"username": request.session["pending_username"].capitalize()})

@app.post("/auth/register")
async def register(request: Request, email: str = Form(), password: str = Form(), repeat_password: str = Form()):
    username = request.session.get("pending_username")
    if not username:
        return RedirectResponse(url="/", status_code=303)
    if password != repeat_password:
        return templates.TemplateResponse(request=request, name=f"error.html", context={"error":f"Wachtwoorden komen niet overeen."})
    
    hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    try:
        execute_sql("""
                INSERT INTO users (username, email, hashed_password)
                VALUES (?, ?, ?);
                """,
                (username, email, hashed_password))
    except Exception as e:
        raise HTTPException(500, f"Failed to execute: {e}")
    
    request.session.clear()
    request.session["username"] = username
    return RedirectResponse(url="/", status_code=303)

@app.get("/auth/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)

@app.get("/lijstjes")
async def lijstjes(request: Request):
    user = request.session.get("username")

    rows = execute_sql("SELECT username, lijstje_link FROM users;")

    return templates.TemplateResponse(request=request, name="lijstjes.html", context={"logged_in_user":user, "accounts":rows})

@app.post("/lijstjes/bewerk")
async def lijstje_bewerken(request: Request, lijstje_link: str = Form("")):
    user = request.session.get("username")
    if not user:
        return templates.TemplateResponse(request=request, name="logged_out.html")

    link = lijstje_link.strip()
    if link:
        if "://" not in link:
            link = "https://" + link
        parsed = urlparse(link)
        if parsed.scheme not in ("http", "https") or not parsed.netloc or len(link) > 500:
            return templates.TemplateResponse(
                request=request, name="error.html", status_code=400,
                context={"error": "Dat is geen geldige link."}
            )
    else:
        link = None

    execute_sql("UPDATE users SET lijstje_link = ? WHERE username = ?;", (link, user.lower()))
    return RedirectResponse("/lijstjes", status_code=303)

@app.get("/")
def home(request: Request):
    user = request.session.get("username")
    if user:
        rows = execute_sql("SELECT lootje1, lootje2, rolled FROM users WHERE username = ?;", (user.lower(),))
        return templates.TemplateResponse(
            request=request, name="lootjes.html",
            context={
                "lootje1": decrypt(rows[0][0]),
                "lootje2": decrypt(rows[0][1]),
                "rolled": rows[0][2] != 0,
                "logged_in_user": user.capitalize(),
            },
        )
    else:
        return templates.TemplateResponse(request=request, name=f"login.html")

@app.get("/lootjestrekken", response_class=HTMLResponse)
async def lootjes_trekken_page(request: Request):
    user = request.session.get("username")
    if user == "leon":
        return templates.TemplateResponse(request=request, name="lootjestrekken.html")
    else:
        return templates.TemplateResponse(request=request, name="error.html", context={"error":"403: Geen toestemming"})

@app.get("/berichten")
async def berichten_page(request: Request):
    user = request.session.get("username")
    if not user:
        return templates.TemplateResponse(
            request=request, name=f"logged_out.html"
        )
    else:
        rows = execute_sql("SELECT username FROM users;")
        accounts = []
        for row in rows:
            accounts.append(row[0])

        return templates.TemplateResponse(
            request=request, name=f"berichten.html", context={"logged_in_user":user.capitalize(), "accounts":rows}
        )

@app.post("/berichten/verstuur")
async def verstuur_bericht(request: Request, message: str = Form(), send_to_dropdown: str = Form()):
    user = request.session.get("username")
    if not user:
        return templates.TemplateResponse(
            request=request, name=f"logged_out.html"
        )
    else:
        name = send_to_dropdown.lower().capitalize()

        sender = get_user(user)
        recipient_rows = execute_sql("SELECT email FROM users WHERE username = ?;", (send_to_dropdown.strip().lower(),))
        if not sender or not recipient_rows:
            return templates.TemplateResponse(
                request=request, name="error.html", status_code=400, context={"error":"Ontvanger niet gevonden."}
            )

        token = create_message(sender[0], name, recipient_rows[0][0], message)
        reply_url = f"{settings.BASE_URL}/reageer/{token}"

        text_body, html_body = build_email(name, message, reply_url)
        send_email(f"{recipient_rows[0][0]}", "Anoniem bericht Sinterklaas", text_body, html_body)
        return templates.TemplateResponse(request=request, name=f"email_sent.html", context={"logged_in_user":user})

@app.get("/reageer/{token}", response_class=HTMLResponse)
async def reageer_form(request: Request, token: str):
    msg = get_open_message(token)
    response = templates.TemplateResponse(
        request=request, name="reply.html", context={"token": token, "original": msg[4]}
    )
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Robots-Tag"] = "noindex"
    return response

@app.post("/reageer/{token}", response_class=HTMLResponse)
async def reageer_verstuur(request: Request, token: str, reply: str = Form()):
    reply = reply.strip()
    if not reply or len(reply) > 5000:
        return templates.TemplateResponse(
            request=request, name="error.html", status_code=400,
            context={"error":"Je reactie moet tussen 1 en 5000 tekens zijn."}
        )

    msg = get_open_message(token)
    message_id, sender_id, recipient_name, original = msg[0], msg[2], msg[3], msg[4]

    execute_sql("UPDATE messages SET replied_at = CURRENT_TIMESTAMP WHERE id = ?;", (message_id,))

    sender_rows = execute_sql("SELECT email FROM users WHERE user_id = ?;", (sender_id,))
    text_body, html_body = build_reply_email(recipient_name, original, reply)
    ok = bool(sender_rows) and send_email(
        sender_rows[0][0], f"{recipient_name} heeft gereageerd op je anonieme bericht", text_body, html_body
    )

    if not ok:
        execute_sql("UPDATE messages SET replied_at = NULL WHERE id = ?;", (message_id,))
        return templates.TemplateResponse(
            request=request, name="error.html", status_code=502,
            context={"error":"Verzenden mislukt, probeer het later opnieuw."}
        )

    return templates.TemplateResponse(
        request=request, name="template.html", context={"text":"Je reactie is verstuurd."}
    )


@app.get("/treklootjes", response_class=HTMLResponse)
async def lootjes_trekken(request: Request):
    user = request.session.get("username")
    if user == "leon":
        lootje1 = settings.NAMES.copy()
        lootje2 = settings.NAMES.copy()

        done = False

        while not done:
            random.shuffle(lootje1)
            random.shuffle(lootje2)
            try:
                for i in range(len(settings.NAMES)):
                    if settings.NAMES[i] == lootje1[i] or settings.NAMES[i] == lootje2[i] or lootje1[i] == lootje2[i]:
                        raise
                    else:
                        if lootje1[i] in settings.EXCLUSIONS[settings.NAMES[i]]:
                            raise
                done = True
            except KeyError:
                return "Internal server error"
            except:
                pass

        rows = execute_sql("SELECT username FROM users;")
        if len(rows) == len(settings.NAMES):
            for i in range(len(settings.NAMES)):
                execute_sql(
                    "UPDATE users SET lootje1 = ?, lootje2 = ? WHERE username = ?",
                    (encrypt(lootje1[i]), encrypt(lootje2[i]), settings.NAMES[i]),
                )
            return templates.TemplateResponse(request=request, name=f"template.html", context={"text":"Lootjes zijn getrokken."})
        else:
            print(len(rows))
            if len(rows) == 1:
                error = f"Nog niet iedereen heeft een account. {len(settings.NAMES) - len(rows)} resterend.\n\nAlleen {rows[0][0].capitalize()} heeft een account"
            elif len(rows) == 0:
                error = f"Nog niemand heeft een account. {len(settings.NAMES) - len(rows)} resterend."
            else:
                error = f"Nog niet iedereen heeft een account. {len(settings.NAMES) - len(rows)} resterend.\n\n{', '.join([x[0].capitalize() for x in rows][:-1])} en {[x[0].capitalize() for x in rows][-1]} hebben al een account."
            return templates.TemplateResponse(request=request, name=f"error.html", context={"error":error})

    else:
        return templates.TemplateResponse(request=request, name="error.html", context={"error":"403: Geen toestemming"})

@app.post("/api/mark-rolled")
async def mark_rolled(request: Request):
    user = request.session.get("username")
    if not user:
        raise HTTPException(status_code=401, detail="Not logged in")
    
    try:
        execute_sql("UPDATE users SET rolled = 1 WHERE username = ?;", (user.lower(),))
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))