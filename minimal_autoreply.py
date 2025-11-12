import os, re, csv, uuid, imaplib
from datetime import datetime
from typing import Optional, Dict, Any
from email.header import decode_header, make_header
from email import policy
from email.parser import BytesParser
from bs4 import BeautifulSoup
import argparse

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")

IMAP_HOST = os.environ.get("IMAP_HOST", "imap.gmail.com")
IMAP_USER = os.environ.get("IMAP_USER", "")
IMAP_PASS = os.environ.get("IMAP_PASS", "")

FROM_EMAIL = os.environ.get("FROM_EMAIL", "")
FROM_NAME  = os.environ.get("FROM_NAME", "SDR Bot")
TEST_TO    = os.environ.get("TEST_TO", "")

LOG_FILE  = os.environ.get("LOG_FILE", "mails_log.csv")
SEEN_FILE = os.environ.get("SEEN_FILE", "inbound_seen.csv")


from openai import OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)

import sendgrid
from sendgrid.helpers.mail import Mail, From, To, Content, Email


def ensure_csv_init():
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["ts","direction","thread_id","to","subject","variant","status","note"])
    if not os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(["msg_uid"])

def new_thread_id() -> str:
    return uuid.uuid4().hex[:12].upper()

def inject_tracking_footer(html_body: str, thread_id: str) -> str:
    footer = f"""
    <hr style="border:none;border-top:1px solid #eee;margin:16px 0;" />
    <div style="font-size:12px;color:#888;">
      Ref: <b>[TID:{thread_id}]</b><br/>
      If you prefer not to hear from us, reply "unsubscribe".
    </div>
    <!-- TID:{thread_id} -->
    """
    return html_body + footer

def send_html_email_with_thread(
    to_email: str,
    subject: str,
    html_body: str,
    from_email: str = FROM_EMAIL,
    from_name: str = FROM_NAME,
    thread_id: Optional[str] = None,
    variant: str = "A",
) -> Dict[str, Any]:
    assert SENDGRID_API_KEY, "SENDGRID_API_KEY missing"
    thread_id = thread_id or new_thread_id()
    html = inject_tracking_footer(html_body, thread_id)

    sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_API_KEY)
    mail = Mail(
        from_email=From(from_email, from_name),
        to_emails=To(to_email),
        subject=subject,
        html_content=Content("text/html", html),
    )

    if IMAP_USER:
        mail.reply_to = Email(IMAP_USER)

    resp = sg.client.mail.send.post(request_body=mail.get())

    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            datetime.utcnow().isoformat(), "outbound", thread_id, to_email, subject, variant,
            f"sg:{resp.status_code}", "sent"
        ])
    return {"status": "ok", "thread_id": thread_id, "http_status": resp.status_code}


TID_PATTERN = re.compile(r"TID:([A-Z0-9]{12})")

def _get_msg_text(msg) -> str:
    text = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                text += part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="ignore") + "\n"
    else:
        if msg.get_content_type() == "text/plain":
            text += msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", errors="ignore")
    if not text:
        html = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    html += part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="ignore")
        elif msg.get_content_type() == "text/html":
            html = msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", errors="ignore")
        if html:
            text = BeautifulSoup(html, "html.parser").get_text("\n")
    return text.strip()

def _load_seen_uids() -> set:
    with open(SEEN_FILE, "r", newline="", encoding="utf-8") as f:
        return {row[0] for i,row in enumerate(csv.reader(f)) if i>0}

def _append_seen_uid(uid: str):
    with open(SEEN_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([uid])

def poll_inbound_once():
    hits = []
    assert IMAP_HOST and IMAP_USER and IMAP_PASS, "IMAP config missing"
    M = imaplib.IMAP4_SSL(IMAP_HOST)
    M.login(IMAP_USER, IMAP_PASS)
    M.select("INBOX")
    typ, data = M.search(None, 'UNSEEN')
    uids = data[0].split()
    already = _load_seen_uids()

    for uid in uids:
        uid_str = uid.decode()
        if uid_str in already:
            continue
        typ, msg_data = M.fetch(uid, '(RFC822)')
        raw = msg_data[0][1]
        msg = BytesParser(policy=policy.default).parsebytes(raw)

        from_addr = str(make_header(decode_header(msg.get('From',''))))
        subject   = str(make_header(decode_header(msg.get('Subject',''))))
        text      = _get_msg_text(msg)

        m = TID_PATTERN.search(text)
        if m:
            tid = m.group(1)
            hits.append((uid_str, from_addr, subject, tid, text))
        _append_seen_uid(uid_str)
    M.logout()
    return hits


AUTO_REPLY_MODEL = os.environ.get("AUTO_REPLY_MODEL", "gpt-4o-mini")
AUTO_REPLY_SYSTEM = """You are a polite SDR. Write a short, helpful reply (70-120 words), in the same language as the inbound email if possible.
- Acknowledge their message.
- Provide 1 clear answer or propose a quick call.
- Keep it simple, no marketing fluff.
- Sign as: {from_name}, {from_email}
"""

def draft_auto_reply(inbound_text: str, last_subject: str, from_name: str = FROM_NAME, from_email: str = FROM_EMAIL) -> str:
    sys = AUTO_REPLY_SYSTEM.format(from_name=from_name, from_email=from_email)
    user = f"""Inbound subject: {last_subject}
----
Inbound message:
{inbound_text}
----
Write a concise reply. If the inbound says "unsubscribe" (or similar), return exactly: "Not replying per unsubscribe.""""
    resp = client.chat.completions.create(
        model=AUTO_REPLY_MODEL,
        messages=[{"role":"system","content":sys},{"role":"user","content":user}],
        temperature=0.3
    )
    return resp.choices[0].message.content.strip()

def _parse_from_address(raw_from: str) -> str:
    m = re.search(r"<([^>]+)>", raw_from)
    return m.group(1) if m else raw_from

def send_auto_reply(to_addr: str, thread_id: str, inbound_subject: str, inbound_text: str) -> Optional[str]:
    body_text = draft_auto_reply(inbound_text, inbound_subject)
    if body_text.strip().lower() == "not replying per unsubscribe.":
        with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                datetime.utcnow().isoformat(), "auto-skip", thread_id, to_addr, inbound_subject, "", "skipped", "unsubscribe"
            ])
        return None

    subject = inbound_subject if inbound_subject.lower().startswith("re:") else f"Re: {inbound_subject}"
    html = f"<div style='font-family:Inter,Arial,sans-serif;line-height:1.5;white-space:pre-wrap'>{body_text}</div>"

    res = send_html_email_with_thread(
        to_email=to_addr,
        subject=subject,
        html_body=html,
        from_email=FROM_EMAIL,
        from_name=FROM_NAME,
        thread_id=thread_id,
        variant="AUTO"
    )

    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            datetime.utcnow().isoformat(), "auto-reply", thread_id, to_addr, subject, "AUTO", res["status"], "auto_replied"
        ])
    return res["status"]

def handle_inbound_once():
    hits = poll_inbound_once()
    for uid, from_raw, subj, tid, text in hits:
        to_addr = _parse_from_address(from_raw)
        try:
            status = send_auto_reply(to_addr, tid, subj, text)
            print(f"[AUTO] {to_addr} <- {subj} (TID:{tid}) => {status}")
        except Exception as e:
            with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow([
                    datetime.utcnow().isoformat(), "auto-reply", tid, to_addr, subj, "AUTO", "error", repr(e)
                ])
            print(f"[ERROR] auto-reply failed for {to_addr}: {e}")


def cmd_send():
    assert FROM_EMAIL and TEST_TO, "FROM_EMAIL / TEST_TO missing"
    subject = "Quick idea to cut manual ops by 30%"
    html = """
    <div style="font-family:Inter,Arial,sans-serif;line-height:1.6">
      <p>Hi there,</p>
      <p>We built a tiny agent that drafts emails and auto-replies to common questions.
      Teams use it to cut manual ops by ~30% in the first week.</p>
      <p>Worth a 15-min chat to see if it's relevant for you?</p>
      <p>— {from_name}</p>
    </div>
    """.replace("{from_name}", FROM_NAME)
    res = send_html_email_with_thread(TEST_TO, subject, html)
    print("[SEND] status:", res)

def cmd_poll():
    handle_inbound_once()

if __name__ == "__main__":
    ensure_csv_init()
    parser = argparse.ArgumentParser(description="Minimal cold email + auto-reply MVP")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("send", help="Send one test outbound email to TEST_TO")
    sub.add_parser("poll", help="Poll inbox once and auto-reply to matched threads")

    args = parser.parse_args()
    if args.cmd == "send":
        cmd_send()
    elif args.cmd == "poll":
        cmd_poll()
    else:
        parser.print_help()
