"""Web server (standard library only): demo page, owner panel, WhatsApp and Telegram webhooks.

  python3 -m okno.web [--port 8080] [--host 127.0.0.1] [--provider auto]

Routes
  GET  /                       demo: customer chat on the left, the staff card on the right
  POST /api/message, /api/reset
  GET  /admin?token=...        owner panel (needs OKNO_ADMIN_TOKEN): knowledge base and leads
  GET  /api/admin/leads(.csv)  leads from the JSONL file;  POST /api/admin/kb  replace the knowledge base
  GET/POST /webhooks/whatsapp  Meta Cloud API webhook (verify token + X-Hub-Signature-256)
  POST /webhooks/telegram      Telegram webhook (X-Telegram-Bot-Api-Secret-Token)
"""
import argparse
import csv
import io
import json
import os
import pathlib
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import kb as kbmod
from .agent import Conversation
from .channels import telegram as tg
from .channels import whatsapp as wa
from .channels.router import Router
from .handoff import sinks_from_env
from .providers import make_provider


class DemoApp:
    def __init__(self, provider_name="auto", model=None, kb_path=None, sinks=None, env=None,
                 wa_client=None, tg_client=None, async_channels=True):
        self.env = dict(os.environ if env is None else env)
        self.kb_path = pathlib.Path(kb_path or self.env.get("OKNO_KB_PATH") or kbmod.DEFAULT_KB)
        if not self.kb_path.exists():  # first start: begin from the demo knowledge base, then edit in /admin
            self.kb_path.parent.mkdir(parents=True, exist_ok=True)
            self.kb_path.write_text(pathlib.Path(kbmod.DEFAULT_KB).read_text(encoding="utf-8"), encoding="utf-8")
        self.kb = kbmod.load(self.kb_path)
        self.provider_name, self.model = provider_name, model
        self.sinks = sinks if sinks is not None else sinks_from_env()
        self.leads_path = pathlib.Path(self.env.get("OKNO_LEADS_FILE", "data/leads.jsonl"))
        self.sessions, self.lock = {}, threading.Lock()
        self.router = Router(self.kb, provider_name, model, self.sinks)
        self.wa_client = wa_client or wa.WhatsAppClient()
        self.tg_client = tg_client or tg.TelegramClient()
        self.async_channels = async_channels
        probe = make_provider(provider_name, self.kb, model)
        self.provider_label = f"{probe.name} / {probe.model}"

    # demo chat
    def message(self, payload):
        sid = str(payload.get("sid") or uuid.uuid4())
        text = str(payload.get("text", ""))[:1000]
        with self.lock:
            conv = self.sessions.get(sid)
            if conv is None:
                conv = Conversation(self.kb, make_provider(self.provider_name, self.kb, self.model),
                                    channel="web", sinks=self.sinks)
                self.sessions[sid] = conv
        out = conv.handle(text)
        out["sid"] = sid
        return out

    def reset(self, payload):
        with self.lock:
            self.sessions.pop(str(payload.get("sid")), None)
        return {"ok": True}

    def info(self):
        return {"company": self.kb["company"], "fictional": bool(self.kb.get("fictional")),
                "provider": self.provider_label}

    # owner panel
    def admin_ok(self, token):
        expected = self.env.get("OKNO_ADMIN_TOKEN", "")
        return bool(expected) and token == expected

    def leads(self):
        if not self.leads_path.exists():
            return []
        rows = []
        for line in self.leads_path.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return rows[::-1]

    def leads_csv(self):
        fields = ["ts", "reason", "task", "district", "address_hint", "time_window", "name", "phone", "urgent", "channel"]
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(fields)
        for r in self.leads():
            lead = r.get("lead", {})
            w.writerow([r.get("ts", ""), r.get("reason", "")] + [lead.get(f, "") for f in fields[2:]])
        return buf.getvalue()

    def update_kb(self, new_kb):
        tmp = self.kb_path.with_suffix(".tmp.json")
        tmp.write_text(json.dumps(new_kb, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        kbmod.load(tmp)  # raises ValueError if required keys are missing
        tmp.replace(self.kb_path)
        self.kb = kbmod.load(self.kb_path)
        self.router.kb = self.kb  # new conversations use the new rules
        return {"ok": True}

    # channels
    def _run(self, fn):
        if self.async_channels:
            threading.Thread(target=fn, daemon=True).start()
        else:
            fn()

    def whatsapp_inbound(self, payload):
        for m in wa.parse_inbound(payload):
            def work(m=m):
                reply = self.router.handle("whatsapp", m)
                self.wa_client.send_text(m["user"], reply)
            self._run(work)

    def telegram_inbound(self, update):
        m = tg.parse_update(update)
        if m:
            def work():
                reply = self.router.handle("telegram", m)
                self.tg_client.send_text(m["user"], reply)
            self._run(work)


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype="application/json; charset=utf-8"):
            data = body if isinstance(body, bytes) else (
                body.encode("utf-8") if isinstance(body, str) else json.dumps(body, ensure_ascii=False).encode("utf-8"))
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _token(self, query):
            return self.headers.get("X-Okno-Token") or (query.get("token") or [""])[0]

        def do_GET(self):
            url = urlparse(self.path)
            q = parse_qs(url.query)
            if url.path in ("/", "/index.html"):
                return self._send(200, PAGE, "text/html; charset=utf-8")
            if url.path == "/api/info":
                return self._send(200, app.info())
            if url.path == "/webhooks/whatsapp":
                challenge = wa.verify_subscription({k: v[0] for k, v in q.items()},
                                                   app.env.get("WHATSAPP_VERIFY_TOKEN", ""))
                return self._send(200, challenge, "text/plain") if challenge is not None else self._send(403, {"error": "forbidden"})
            if url.path.startswith("/admin") or url.path.startswith("/api/admin"):
                if not app.admin_ok(self._token(q)):
                    return self._send(404, {"error": "not found"})
                if url.path == "/admin":
                    return self._send(200, ADMIN_PAGE, "text/html; charset=utf-8")
                if url.path == "/api/admin/leads":
                    return self._send(200, {"leads": app.leads()})
                if url.path == "/api/admin/leads.csv":
                    return self._send(200, app.leads_csv(), "text/csv; charset=utf-8")
                if url.path == "/api/admin/kb":
                    return self._send(200, app.kb)
            return self._send(404, {"error": "not found"})

        def do_POST(self):
            url = urlparse(self.path)
            length = min(int(self.headers.get("Content-Length", 0) or 0), 200000)
            raw = self.rfile.read(length) if length else b""
            try:
                payload = json.loads(raw or b"{}")
            except (ValueError, json.JSONDecodeError):
                return self._send(400, {"error": "invalid JSON"})
            if url.path == "/api/message":
                return self._send(200, app.message(payload))
            if url.path == "/api/reset":
                return self._send(200, app.reset(payload))
            if url.path == "/webhooks/whatsapp":
                if not wa.verify_signature(app.env.get("WHATSAPP_APP_SECRET", ""), raw,
                                           self.headers.get("X-Hub-Signature-256", "")):
                    return self._send(403, {"error": "bad signature"})
                app.whatsapp_inbound(payload)
                return self._send(200, {"ok": True})
            if url.path == "/webhooks/telegram":
                if not tg.verify_secret(app.env.get("TELEGRAM_WEBHOOK_SECRET", ""),
                                        self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")):
                    return self._send(403, {"error": "bad secret"})
                app.telegram_inbound(payload)
                return self._send(200, {"ok": True})
            if url.path == "/api/admin/kb":
                if not app.admin_ok(self._token(parse_qs(url.query))):
                    return self._send(404, {"error": "not found"})
                try:
                    return self._send(200, app.update_kb(payload))
                except (ValueError, KeyError) as e:
                    return self._send(400, {"error": f"invalid knowledge base: {e}"})
            return self._send(404, {"error": "not found"})

        def log_message(self, fmt, *args):  # keep the console quiet
            pass
    return Handler


def make_server(host="127.0.0.1", port=8080, provider_name="auto", model=None, kb_path=None, sinks=None, **kw):
    app = DemoApp(provider_name, model, kb_path, sinks, **kw)
    return ThreadingHTTPServer((host, port), make_handler(app)), app


def main(argv=None):
    ap = argparse.ArgumentParser(description="Okno web server")
    ap.add_argument("--host", default="127.0.0.1", help="0.0.0.0 to open from a phone on the same Wi-Fi")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--provider", default=os.environ.get("OKNO_PROVIDER", "auto"))
    ap.add_argument("--model", default=None)
    ap.add_argument("--kb", default=None)
    args = ap.parse_args(argv)
    server, app = make_server(args.host, args.port, args.provider, args.model, args.kb)
    print(f"Okno: http://{args.host}:{args.port}  ({app.provider_label}). Ctrl+C — стоп.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


ADMIN_PAGE = r"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Okno — кабинет</title>
<style>
:root{--bg:#f3f4f1;--panel:#fff;--ink:#1d2321;--soft:#5d6763;--line:#dde2de;--accent:#1f6f5c;--accent-ink:#fff;--bad:#9a3b12}
@media (prefers-color-scheme: dark){:root{--bg:#121614;--panel:#1a201d;--ink:#e6ece9;--soft:#9aa7a1;--line:#2b3430;--accent:#5cc3a3;--accent-ink:#0d1210;--bad:#f0a070}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:1100px;margin:0 auto;padding:16px;display:grid;gap:16px}
section{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px;min-width:0}
h1{font-size:20px;margin:0}h2{font-size:16px;margin:0 0 10px}
textarea{width:100%;min-height:320px;font:13px/1.4 ui-monospace,Menlo,Consolas,monospace;background:var(--bg);color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:10px}
button,a.btn{background:var(--accent);color:var(--accent-ink);border:0;border-radius:8px;padding:8px 14px;font:inherit;font-weight:600;cursor:pointer;text-decoration:none;display:inline-block}
.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:8px}
.msg{color:var(--soft)}.err{color:var(--bad)}
.tw{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
</style></head><body><main>
<h1>Okno — кабинет компании</h1>
<section><h2>Заявки</h2><div class="row"><a class="btn" id="csv" href="#">Скачать CSV</a><span class="msg" id="count"></span></div>
<div class="tw"><table><thead><tr><th>Когда</th><th>Тип</th><th>Задача</th><th>Район</th><th>Время</th><th>Имя</th><th>Телефон</th></tr></thead><tbody id="leads"></tbody></table></div></section>
<section><h2>База знаний (услуги, районы, график, ответы)</h2><textarea id="kb" spellcheck="false" aria-label="База знаний в формате JSON"></textarea>
<div class="row"><button id="save">Сохранить</button><span id="kbmsg" class="msg">Изменения действуют для новых диалогов.</span></div></section>
</main><script>
const token=new URLSearchParams(location.search).get('token')||'';const H={'X-Okno-Token':token,'Content-Type':'application/json'};
document.getElementById('csv').href='/api/admin/leads.csv?token='+encodeURIComponent(token);
fetch('/api/admin/leads',{headers:H}).then(r=>r.json()).then(d=>{const tb=document.getElementById('leads');document.getElementById('count').textContent='Всего: '+d.leads.length;
 d.leads.forEach(x=>{const l=x.lead||{};const tr=document.createElement('tr');[x.ts,x.reason,l.task,l.district,l.time_window,l.name,l.phone].forEach(v=>{const td=document.createElement('td');td.textContent=v||'';tr.appendChild(td)});tb.appendChild(tr)})});
fetch('/api/admin/kb',{headers:H}).then(r=>r.json()).then(k=>{document.getElementById('kb').value=JSON.stringify(k,null,2)});
document.getElementById('save').addEventListener('click',async()=>{const m=document.getElementById('kbmsg');let body;
 try{body=JSON.parse(document.getElementById('kb').value)}catch(e){m.textContent='Ошибка в JSON: '+e.message;m.className='err';return}
 const r=await fetch('/api/admin/kb',{method:'POST',headers:H,body:JSON.stringify(body)});const o=await r.json();
 m.textContent=r.ok?'Сохранено. Новые диалоги используют новые правила.':('Не сохранено: '+o.error);m.className=r.ok?'msg':'err';});
</script></body></html>
"""


PAGE = r"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Okno — демо</title>
<style>
:root{--bg:#f3f4f1;--panel:#ffffff;--ink:#1d2321;--soft:#5d6763;--line:#dde2de;--accent:#1f6f5c;--accent-ink:#ffffff;
--bubble:#e7f1ed;--me:#1f6f5c;--me-ink:#ffffff;--warn:#9a3b12;--chip:#eef2ef}
@media (prefers-color-scheme: dark){:root{--bg:#121614;--panel:#1a201d;--ink:#e6ece9;--soft:#9aa7a1;--line:#2b3430;
--accent:#5cc3a3;--accent-ink:#0d1210;--bubble:#22302a;--me:#2f8f75;--me-ink:#ffffff;--warn:#f0a070;--chip:#232c28}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
header{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:baseline;padding:14px 16px;border-bottom:1px solid var(--line);background:var(--panel)}
header h1{margin:0;font-size:18px}
.tag{font-size:12px;padding:2px 8px;border-radius:99px;background:var(--chip);color:var(--soft)}
.note{font-size:13px;color:var(--soft)}
main{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(0,1fr);gap:16px;padding:16px;max-width:1100px;margin:0 auto}
@media (max-width:760px){main{grid-template-columns:minmax(0,1fr)}}
section{background:var(--panel);border:1px solid var(--line);border-radius:12px;display:flex;flex-direction:column;min-width:0}
section h2{margin:0;padding:12px 14px;font-size:14px;border-bottom:1px solid var(--line);color:var(--soft);font-weight:600}
#log{flex:1;min-height:360px;max-height:60vh;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:8px}
.msg{max-width:85%;padding:8px 12px;border-radius:12px;white-space:pre-wrap;word-wrap:break-word}
.bot{background:var(--bubble);align-self:flex-start;border-bottom-left-radius:4px}
.me{background:var(--me);color:var(--me-ink);align-self:flex-end;border-bottom-right-radius:4px}
.chips{display:flex;flex-wrap:wrap;gap:6px;padding:0 14px 10px}
.chips button{border:1px solid var(--line);background:var(--chip);color:var(--ink);border-radius:99px;padding:4px 10px;font:inherit;font-size:13px;cursor:pointer}
form{display:flex;gap:8px;padding:12px 14px;border-top:1px solid var(--line)}
input{flex:1;min-width:0;padding:10px 12px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--ink);font:inherit}
button.primary{background:var(--accent);color:var(--accent-ink);border:0;border-radius:8px;padding:10px 14px;font:inherit;font-weight:600;cursor:pointer}
button:focus-visible,input:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
#card{padding:14px;white-space:pre-wrap;font-size:14px;min-height:120px}
#status{padding:0 14px 14px;font-size:13px;color:var(--soft)}
.empty{color:var(--soft)}
.urgent{color:var(--warn);font-weight:600}
footer{max-width:1100px;margin:0 auto;padding:0 16px 24px;font-size:12px;color:var(--soft)}
</style>
</head>
<body>
<header>
  <h1>Okno</h1><span class="tag">прототип</span>
  <span class="note" id="who">Вымышленная компания</span>
  <span class="note" id="prov"></span>
</header>
<main>
  <section aria-label="Чат клиента">
    <h2>Так видит клиент</h2>
    <div id="log" aria-live="polite"></div>
    <div class="chips" id="chips">
      <button type="button">Течёт смеситель на кухне</button>
      <button type="button">Сколько стоит?</button>
      <button type="button">Бостандыкский район</button>
      <button type="button">Завтра после 18:00</button>
      <button type="button">Сәлеметсіз бе!</button>
      <button type="button">Искрит розетка!</button>
    </div>
    <form id="f"><input id="t" autocomplete="off" placeholder="Напишите как клиент…" aria-label="Сообщение"><button class="primary">Отправить</button></form>
  </section>
  <section aria-label="Карточка для сотрудника">
    <h2>Что получит сотрудник</h2>
    <div id="card" class="empty">Карточка заявки появится, когда агент соберёт данные и клиент их подтвердит.</div>
    <div id="status"></div>
    <form id="r"><button class="primary" type="submit">Новый диалог</button></form>
  </section>
</main>
<footer>Демо Okno. Компания и данные вымышленные. Агент не называет цены и не подтверждает выезд — это делает сотрудник.</footer>
<script>
let sid = null;
const log = document.getElementById('log'), card = document.getElementById('card'), st = document.getElementById('status');
function bubble(text, cls){const d=document.createElement('div');d.className='msg '+cls;d.textContent=text;log.appendChild(d);log.scrollTop=log.scrollHeight;}
function fields(lead){const L={task:'Задача',district:'Район',address_hint:'Ориентир',time_window:'Удобное время',name:'Имя',phone:'Телефон'};
  return Object.keys(L).filter(k=>lead[k]).map(k=>L[k]+': '+lead[k]).join('\n');}
async function send(text){
  if(!text.trim())return; bubble(text,'me');
  const r = await fetch('/api/message',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sid,text})});
  const o = await r.json(); sid=o.sid; bubble(o.reply,'bot');
  if(o.card){card.textContent=o.card;card.className=o.lead.urgent?'urgent':'';}
  else{const f=fields(o.lead);card.textContent=f?('Собрано (ещё не отправлено):\n'+f):'Карточка заявки появится, когда агент соберёт данные и клиент их подтвердит.';card.className=f?'':'empty';}
  const S={collecting:'собираем данные',confirming:'ждём подтверждения клиента',needs_phone:'нужен телефон',handed_off:'передано сотруднику',closed:'диалог закрыт'};
  st.textContent='Статус: '+(S[o.status]||o.status)+(o.missing&&o.missing.length&&o.status!=='handed_off'?' · не хватает: '+o.missing.join(', '):'');
}
document.getElementById('f').addEventListener('submit',e=>{e.preventDefault();const t=document.getElementById('t');const v=t.value;t.value='';send(v);});
document.getElementById('chips').addEventListener('click',e=>{if(e.target.tagName==='BUTTON')send(e.target.textContent);});
document.getElementById('r').addEventListener('submit',async e=>{e.preventDefault();if(sid)await fetch('/api/reset',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sid})});
  sid=null;log.innerHTML='';card.textContent='Карточка заявки появится, когда агент соберёт данные и клиент их подтвердит.';card.className='empty';st.textContent='';});
fetch('/api/info').then(r=>r.json()).then(i=>{document.getElementById('who').textContent=(i.fictional?'Вымышленная компания «':'«')+i.company+'»';
  document.getElementById('prov').textContent='Режим: '+i.provider+(i.provider.startsWith('offline')?' (без модели)':'');});
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
