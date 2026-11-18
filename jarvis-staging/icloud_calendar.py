"""Read-only iCloud CalDAV access for an authenticated JARVIS session."""
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from threading import Lock, Timer
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

import httpx
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field, SecretStr

BASE = "https://caldav.icloud.com/"
NS = {"d": "DAV:", "c": "urn:ietf:params:xml:ns:caldav"}
TZ = ZoneInfo("America/Puerto_Rico")
sessions = {}
lock = Lock()


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: SecretStr


class Selection(BaseModel):
    connection: str = Field(max_length=100)
    calendar: str = Field(default="", max_length=100)


def apple_url(base, href):
    url = urljoin(base, href)
    p = urlsplit(url)
    if (p.scheme != "https" or p.username or p.password or p.port not in (None, 443)
            or not re.fullmatch(r"(?:p[0-9]+-)?caldav\.icloud\.com", p.hostname or "")):
        raise ValueError("Invalid calendar host")
    return url


def query(client, method, url, body, depth):
    for _ in range(4):
        with client.stream(method, url, content=body, headers={"Depth": depth, "Content-Type": "application/xml; charset=utf-8"}) as res:
            if res.is_redirect:
                url = apple_url(url, res.headers["location"])
                continue
            if res.status_code in (401, 403):
                raise HTTPException(403, "iCloud no autorizó la lectura. Revisa tu contraseña específica de app.")
            if res.status_code != 207:
                raise ValueError("Unexpected CalDAV response")
            buf = bytearray()
            for chunk in res.iter_bytes():
                buf.extend(chunk)
                if len(buf) > 2_000_000:
                    raise ValueError("Calendar too large")
            raw = buf.decode("utf-8-sig")
            if "<!" in raw.upper() and re.search(r"<!\s*(DOCTYPE|ENTITY)", raw, re.I):
                raise ValueError("Unsupported XML")
            root = ET.fromstring(raw)
            if root.tag != "{DAV:}multistatus":
                raise ValueError("Unexpected response")
            return url, root
    raise ValueError("Redirect limit")


def props(client, url, fields, depth="0"):
    return query(client, "PROPFIND", url, f'<d:propfind xmlns:d="DAV:" xmlns:c="{NS["c"]}"><d:prop>{fields}</d:prop></d:propfind>', depth)


def success_props(response):
    for ps in response.findall("d:propstat", NS):
        if " 200 " in (ps.findtext("d:status", "", NS) + " "):
            yield ps.find("d:prop", NS)


def discover(client):
    url = BASE
    for tag in ("d:current-user-principal", "c:calendar-home-set"):
        url, root = props(client, url, f"<{tag}/>")
        links = [p.findtext(tag + "/d:href", namespaces=NS) for r in root.findall("d:response", NS) for p in success_props(r)]
        url = apple_url(url, next(link for link in links if link))
    url, root = props(client, url, "<d:resourcetype/><d:displayname/>", "1")
    calendars = {}
    for r in root.findall("d:response", NS):
        for p in success_props(r):
            if p.find("d:resourcetype/c:calendar", NS) is not None:
                calendars[secrets.token_urlsafe(12)] = (p.findtext("d:displayname", "iCloud", NS), apple_url(url, r.findtext("d:href", namespaces=NS)))
    return calendars


def read_today(client, url):
    now = datetime.now(TZ)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    fmt = "%Y%m%dT%H%M%SZ"
    span = 'start="{}" end="{}"'.format(*(x.astimezone(timezone.utc).strftime(fmt) for x in (start, end)))
    body = f'<c:calendar-query xmlns:d="DAV:" xmlns:c="{NS["c"]}"><d:prop><c:calendar-data><c:expand {span}/></c:calendar-data></d:prop><c:filter><c:comp-filter name="VCALENDAR"><c:comp-filter name="VEVENT"><c:time-range {span}/></c:comp-filter></c:comp-filter></c:filter></c:calendar-query>'
    _, root = query(client, "REPORT", url, body, "1")
    rows = []
    for r in root.findall("d:response", NS):
        data = next((p.findtext("c:calendar-data", namespaces=NS) for p in success_props(r) if p.find("c:calendar-data", NS) is not None), None)
        if not data:
            raise ValueError("Incomplete response")
        lines = re.sub(r"\n[ \t]", "", data.replace("\r\n", "\n"))
        events = re.findall(r"(?m)^BEGIN:VEVENT\n(.*?)^END:VEVENT$", lines, re.S | re.M)
        if not events:
            raise ValueError("Missing expanded events")
        for event in events:
            event = re.sub(r"(?ms)^BEGIN:VALARM\n.*?^END:VALARM\n", "", event)
            if re.search(r"(?m)^STATUS:CANCELLED$", event):
                continue
            if re.search(r"(?m)^(RRULE|RDATE)[;:]", event):
                raise ValueError("Unexpanded recurrence")
            dt = re.search(r"(?m)^DTSTART(?:;VALUE=DATE)?:([0-9TZ]+)$", event)
            if not dt:
                raise ValueError("Unverified time zone")
            raw = dt[1]
            when = (datetime.strptime(raw, "%Y%m%d").date().isoformat() if len(raw)==8 else
                    datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc).astimezone(TZ).isoformat())
            title = re.search(r"(?m)^SUMMARY(?:;[^:\n]*)?:(.*)$", event)
            name = re.sub(r"\\[nN]", " ", title[1]) if title else "Evento"
            rows.append({"start": when, "title": " ".join(name.replace(r"\,", ",").split())[:180]})
    return {"events": sorted(rows, key=lambda row: row["start"]), "checked": datetime.now(TZ).isoformat()}


def remote(credentials, fn):
    try:
        with httpx.Client(auth=credentials, timeout=8, trust_env=False) as client:
            return fn(client)
    except (httpx.HTTPError, ValueError, ET.ParseError, KeyError, StopIteration, TypeError):
        raise HTTPException(502, "No se pudo verificar el calendario de iCloud.") from None


def forget(token):
    with lock:
        sessions.pop(token, None)


def register(app, authenticate):
    @app.post("/v1/calendar/icloud/connect")
    def connect(data: Credentials, user=Depends(authenticate)):
        pwd = data.password.get_secret_value().strip()
        if not re.fullmatch(r"[a-zA-Z]{4}(?:-[a-zA-Z]{4}){3}", pwd):
            raise HTTPException(400, "Usa una contraseña específica de app de Apple.")
        creds = (data.email.strip(), pwd)
        choices = remote(creds, discover)
        if not choices:
            raise HTTPException(404, "No se encontraron calendarios de iCloud.")
        token = secrets.token_urlsafe(32)
        with lock:
            for old in [key for key, row in sessions.items() if row[0] == user["id"]]:
                sessions.pop(old)
            sessions[token] = (user["id"], time.monotonic()+1800, creds, choices)
        timer = Timer(1800, forget, args=(token,))
        timer.daemon = True
        timer.start()
        return {"connection": token, "calendars": [{"id": k, "name": v[0]} for k,v in choices.items()]}

    def lookup(data, user):
        with lock:
            row = sessions.get(data.connection)
        if not row or row[0] != user["id"] or row[1] <= time.monotonic():
            raise HTTPException(410, "Vuelve a conectar iCloud.")
        return row

    @app.post("/v1/calendar/icloud/today")
    def today(data: Selection, user=Depends(authenticate)):
        row = lookup(data, user)
        choice = row[3].get(data.calendar)
        if not choice:
            raise HTTPException(400, "Selecciona un calendario.")
        return remote(row[2], lambda client: read_today(client, choice[1]))

    @app.post("/v1/calendar/icloud/disconnect")
    def disconnect(data: Selection, user=Depends(authenticate)):
        lookup(data, user)
        forget(data.connection)
        return {"disconnected": True}
