#!/usr/bin/env python3
"""Baixa a agenda do Google (endereço secreto em formato iCal), monta os compromissos
dos próximos dias e grava agenda.enc.json criptografado com a senha da agenda.

Variáveis de ambiente:
  ICAL_URL    um ou mais endereços iCal secretos, separados por espaço, vírgula ou quebra de linha
  AGENDA_PASS senha usada para criptografar (a mesma que se digita no painel)
Não usa bibliotecas externas além de "cryptography".
"""
import base64
import json
import os
import re
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")
WINDOW_DAYS = 14
ITERATIONS = 250000
WD = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "jarvis-agenda/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def unfold(text):
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\n[ \t]", "", text)


def unescape(v):
    return v.replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")


def parse_prop(line):
    head, _, value = line.partition(":")
    parts = head.split(";")
    params = {}
    for p in parts[1:]:
        k, _, v = p.partition("=")
        params[k.upper()] = v.strip('"')
    return parts[0].upper(), params, value


def parse_dt(value, params):
    """Retorna (date | datetime com fuso, dia_inteiro)."""
    value = value.strip()
    if params.get("VALUE") == "DATE" or (len(value) == 8 and "T" not in value):
        return datetime.strptime(value[:8], "%Y%m%d").date(), True
    if value.endswith("Z"):
        return datetime.strptime(value[:-1], "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc), False
    tz = TZ
    if params.get("TZID"):
        try:
            tz = ZoneInfo(params["TZID"])
        except Exception:
            tz = TZ
    return datetime.strptime(value, "%Y%m%dT%H%M%S").replace(tzinfo=tz), False


def parse_trigger(value):
    m = re.match(r"^(-)?P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$", value.strip())
    if not m or not m.group(1):
        return None
    w, d, h, mi, s = (int(x) if x else 0 for x in m.groups()[1:])
    minutes = w * 7 * 1440 + d * 1440 + h * 60 + mi + s // 60
    return minutes if minutes > 0 else None


def parse_rrule(value):
    out = {}
    for part in value.split(";"):
        k, _, v = part.partition("=")
        out[k.upper()] = v
    return out


def parse_events(text):
    events, stack = [], []
    for line in unfold(text).split("\n"):
        if not line.strip():
            continue
        if line.startswith("BEGIN:"):
            name = line[6:].strip()
            stack.append(name)
            if name == "VEVENT":
                events.append({"alarms": [], "exdates": []})
            continue
        if line.startswith("END:"):
            if stack:
                stack.pop()
            continue
        if not events or "VEVENT" not in stack:
            continue
        name, params, value = parse_prop(line)
        ev = events[-1]
        if "VALARM" in stack:
            if name == "TRIGGER" and params.get("RELATED", "START") == "START":
                m = parse_trigger(value)
                if m:
                    ev["alarms"].append(m)
            continue
        if name == "UID":
            ev["uid"] = value.strip()
        elif name == "SUMMARY":
            ev["summary"] = unescape(value)
        elif name == "LOCATION":
            ev["location"] = unescape(value)
        elif name == "STATUS":
            ev["status"] = value.strip().upper()
        elif name == "DTSTART":
            ev["start"], ev["allday"] = parse_dt(value, params)
        elif name == "DTEND":
            ev["end"], _ = parse_dt(value, params)
        elif name == "DURATION":
            ev["duration_raw"] = value.strip()
        elif name == "RRULE":
            ev["rrule"] = parse_rrule(value)
        elif name == "EXDATE":
            for v in value.split(","):
                ev["exdates"].append(parse_dt(v, params)[0])
        elif name == "RECURRENCE-ID":
            ev["rid"] = parse_dt(value, params)[0]
    return [e for e in events if "start" in e]


def norm_key(x):
    if isinstance(x, datetime):
        return ("dt", x.astimezone(timezone.utc).strftime("%Y%m%dT%H%M"))
    return ("d", x.isoformat())


def duration_of(ev):
    start, end = ev["start"], ev.get("end")
    if end is not None:
        return end - start
    raw = ev.get("duration_raw")
    if raw:
        m = re.match(r"^P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$", raw)
        if m:
            w, d, h, mi, s = (int(x) if x else 0 for x in m.groups())
            return timedelta(weeks=w, days=d, hours=h, minutes=mi, seconds=s)
    return timedelta(days=1) if ev.get("allday") else timedelta(0)


def add_months(y, m, n):
    t = y * 12 + (m - 1) + n
    return t // 12, t % 12 + 1


def nth_weekday(y, m, wd, n):
    """n-ésimo dia da semana do mês (n negativo conta do fim). None se não existir."""
    if n > 0:
        d = date(y, m, 1)
        d += timedelta(days=(wd - d.weekday()) % 7)
        d += timedelta(weeks=n - 1)
        return d if d.month == m else None
    ny, nm = add_months(y, m, 1)
    d = date(ny, nm, 1) - timedelta(days=1)
    d -= timedelta(days=(d.weekday() - wd) % 7)
    d -= timedelta(weeks=-n - 1)
    return d if d.month == m else None


def period_dates(rule, base, n):
    """Datas candidatas do período n da recorrência, em ordem."""
    freq = rule.get("FREQ", "")
    interval = int(rule.get("INTERVAL", "1") or 1)
    byday = [x for x in rule.get("BYDAY", "").split(",") if x]
    if freq == "DAILY":
        return [base + timedelta(days=n * interval)]
    if freq == "WEEKLY":
        wk = base - timedelta(days=base.weekday()) + timedelta(weeks=n * interval)
        days = sorted(WD[re.sub(r"[+-]?\d+", "", b)] for b in byday) if byday else [base.weekday()]
        return [wk + timedelta(days=d) for d in days]
    if freq == "MONTHLY":
        y, m = add_months(base.year, base.month, n * interval)
        out = []
        if byday:
            for b in byday:
                mm = re.match(r"^([+-]?\d+)?(MO|TU|WE|TH|FR|SA|SU)$", b)
                if not mm:
                    continue
                ordn = int(mm.group(1)) if mm.group(1) else None
                if ordn is None:
                    d = date(y, m, 1)
                    d += timedelta(days=(WD[mm.group(2)] - d.weekday()) % 7)
                    while d.month == m:
                        out.append(d)
                        d += timedelta(days=7)
                else:
                    d = nth_weekday(y, m, WD[mm.group(2)], ordn)
                    if d:
                        out.append(d)
        else:
            days = [int(x) for x in rule["BYMONTHDAY"].split(",")] if rule.get("BYMONTHDAY") else [base.day]
            for dd in days:
                try:
                    out.append(date(y, m, dd))
                except ValueError:
                    pass
        return sorted(out)
    if freq == "YEARLY":
        y = base.year + n * interval
        try:
            return [date(y, base.month, base.day)]
        except ValueError:
            return []
    return []


def expand(ev, w0, w1, skip_keys):
    """Ocorrências (início, fim) do evento dentro da janela [w0, w1)."""
    dur = duration_of(ev)
    start = ev["start"]
    rule = ev.get("rrule")
    allday = ev.get("allday", False)

    def overlaps(s, e):
        if allday:
            sd, ed = s, e
            return ed > w0.date() and sd < w1.date()
        return e > w0 and s < w1

    if not rule:
        end = start + dur
        return [(start, end)] if overlaps(start, end) else []

    if rule.get("FREQ") not in ("DAILY", "WEEKLY", "MONTHLY", "YEARLY"):
        end = start + dur
        return [(start, end)] if overlaps(start, end) else []

    base = start if allday else start.date()
    count = int(rule["COUNT"]) if rule.get("COUNT") else None
    until = None
    if rule.get("UNTIL"):
        u, _ = parse_dt(rule["UNTIL"], {})
        until = u
    ex = {norm_key(x) for x in ev["exdates"]}
    out, seen = [], 0
    for n in range(0, 5000):
        dates = period_dates(rule, base, n)
        if dates and min(dates) > (w1.date() + timedelta(days=1)):
            break
        for d in dates:
            if d < base:
                continue
            if allday:
                s = d
            else:
                s = datetime.combine(d, start.timetz().replace(tzinfo=None), tzinfo=start.tzinfo)
            seen += 1
            if count is not None and seen > count:
                return out
            if until is not None:
                cmp = s if not allday else datetime.combine(s, datetime.min.time(), tzinfo=timezone.utc)
                cu = until if isinstance(until, datetime) else datetime.combine(until, datetime.max.time(), tzinfo=timezone.utc)
                if cmp > cu:
                    return out
            key = norm_key(s)
            if key in ex or key in skip_keys:
                continue
            e = s + dur
            if overlaps(s, e):
                out.append((s, e))
    return out


def iso_local(x):
    return x.astimezone(TZ).isoformat(timespec="seconds")


def build(texts, now=None):
    now = now or datetime.now(TZ)
    w0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    w1 = w0 + timedelta(days=WINDOW_DAYS)
    result = []
    for text in texts:
        events = parse_events(text)
        overrides = {}
        for ev in events:
            if "rid" in ev and ev.get("uid"):
                overrides.setdefault(ev["uid"], set()).add(norm_key(ev["rid"]))
        for ev in events:
            if ev.get("status") == "CANCELLED":
                continue
            skip = overrides.get(ev.get("uid"), set()) if "rid" not in ev else set()
            alarms = sorted(set(ev["alarms"]), reverse=True) or [30]
            for s, e in expand(ev, w0, w1, skip):
                allday = ev.get("allday", False)
                day = s if allday else s.astimezone(TZ).date()
                item = {
                    "id": "%s|%s" % (ev.get("uid", "sem-id"), norm_key(s)[1]),
                    "title": ev.get("summary", "Sem título"),
                    "start": s.isoformat() if allday else iso_local(s),
                    "end": e.isoformat() if allday else iso_local(e),
                    "allDay": allday,
                    "location": ev.get("location", ""),
                    "link": "https://calendar.google.com/calendar/u/0/r/week/%d/%d/%d" % (day.year, day.month, day.day),
                    "reminders": [] if allday else alarms,
                }
                result.append(item)
    result.sort(key=lambda x: (x["start"], x["title"]))
    return result


def encrypt(plaintext, password):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    salt, iv = os.urandom(16), os.urandom(12)
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITERATIONS).derive(password.encode("utf-8"))
    ct = AESGCM(key).encrypt(iv, plaintext.encode("utf-8"), None)
    b64 = lambda b: base64.b64encode(b).decode("ascii")
    return {"v": 1, "iter": ITERATIONS, "salt": b64(salt), "iv": b64(iv), "data": b64(ct)}


def main():
    urls = [u for u in re.split(r"[\s,;]+", os.environ.get("ICAL_URL", "")) if u]
    password = os.environ.get("AGENDA_PASS", "").strip()
    if not urls or not password:
        print("Faltam os segredos ICAL_URL e AGENDA_PASS.", file=sys.stderr)
        sys.exit(1)
    texts = []
    for i, u in enumerate(urls, 1):
        try:
            texts.append(fetch(u))
        except Exception as exc:
            print("Falha ao baixar o calendário %d: %s" % (i, type(exc).__name__), file=sys.stderr)
            sys.exit(1)
    events = build(texts)
    data = {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "calendars": len(urls),
        "windowDays": WINDOW_DAYS,
        "events": events,
    }
    out = os.environ.get("OUT_FILE", "agenda.enc.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(encrypt(json.dumps(data, ensure_ascii=False), password), f)
    print("Agenda atualizada: %d compromissos nos próximos %d dias." % (len(events), WINDOW_DAYS))


if __name__ == "__main__":
    main()
