🚀 Outbound Copilot

An AI-powered outbound sales agent that automatically sends cold emails, detects replies, and writes smart follow-ups.
(MVP built for rapid iteration – fully local, open-source, and extendable.)

🌟 Overview

Outbound Copilot is the first step toward an autonomous AI SDR (Sales Development Representative) —
a system that handles the entire outbound communication loop:

✉️ Send personalized cold emails (via SendGrid)

🔁 Detect inbound replies (via IMAP)

🤖 Auto-reply with context-aware messages (via OpenAI GPT models)

🧾 Log everything locally for analysis and iteration

This repository currently implements the minimal working loop:

“Send → Detect → Understand → Auto-reply → Log”.

✅ Current Features (MVP)
Feature	Description
Cold Email Sending	Sends HTML emails with unique tracking IDs (TID) using SendGrid
IMAP Inbox Polling	Reads replies from a monitored inbox (e.g., Gmail IMAP)
Reply Detection	Matches inbound emails to outbound threads via embedded TID
Auto-Reply Generation	Uses gpt-4o-mini to draft a polite, short response in the same language
Opt-out Handling	Skips replies containing “unsubscribe” or similar
Local Logging	All messages recorded in mails_log.csv and processed IDs in inbound_seen.csv
CLI Workflow	Simple send and poll commands (python minimal_autoreply.py send/poll)
🧩 Tech Stack
Layer	Tool / Library	Purpose
LLM	OpenAI GPT-4o-mini	Auto-draft replies
Email API	SendGrid	Send HTML emails
Mail Ingestion	IMAP (Gmail, etc.)	Fetch inbound replies
Parsing	BeautifulSoup4	Extract plain text from HTML emails
Runtime	Python 3.12+, virtualenv	Portable local deployment
🗂️ Project Structure
outbound-copilot/
├── minimal_autoreply.py      # Main script (send + poll)
├── requirements.txt
├── .env.example              # Environment template
├── mails_log.csv             # Outbound + auto-reply logs
├── inbound_seen.csv          # Processed message tracking
└── README.md

⚙️ Quickstart
1. Setup environment
python -m venv .venv
source .venv/bin/activate  # (Windows: .\.venv\Scripts\activate)
pip install -r requirements.txt

2. Configure environment

Copy .env.example → .env and fill your values:

OPENAI_API_KEY=sk-xxxx
SENDGRID_API_KEY=SG.xxxx
IMAP_HOST=imap.gmail.com
IMAP_USER=your_inbox@gmail.com
IMAP_PASS=your_app_password
FROM_EMAIL=sales@yourdomain.com
FROM_NAME=Outbound Copilot
TEST_TO=recipient@example.com

3. Run

Send one test email:

python minimal_autoreply.py send


Check inbox, reply to that email, then:

python minimal_autoreply.py poll

🧠 Example Flow
[You]   →  Cold email with unique TID
[Lead]  →  Replies to your email
[Bot]   →  Detects inbound (TID match)
        →  Drafts a short AI reply
        →  Sends via SendGrid
        →  Logs result

🧭 Roadmap (Next Steps)
Stage	Feature	Goal
v0.2	Prospect import (CSV) + bulk send	Handle multiple leads in one run
v0.3	Multi-agent workflow	Sales Agents (3 styles) → Manager → Email Manager handoff
v0.4	Follow-up sequences	Timed steps (Day 1 / Day 3 / Day 7)
v0.5	A/B testing & analytics	Compare subject lines and reply rates
v0.6	CRM sync (HubSpot / Notion)	Push contacts & activities
v0.7	Tracking & pixel analytics	Open/click logging
v1.0	Web dashboard	Full pipeline visibility + manual override
🔒 Notes & Limitations

Gmail accounts require App Passwords
 for IMAP access

SendGrid requires verified sender/domain

No external database yet (CSV-based storage)

LLM replies are deterministic but should be reviewed before production use

💡 Vision

“Outbound Copilot aims to become the Copilot for every SDR —
handling outreach, replies, and scheduling with minimal human effort.”

In the long term, it will evolve into a multi-agent sales workflow:
Sales Agent → Manager Agent → Email Manager → CRM Sync → Sequence Engine.

👤 Author

Beiran Ma (Polimi MSc – AI & Supply Chain Engineer)

💼 Building the Copilot series: SupplyChain Copilot, Documentation Assistant, Outbound Copilot

🌐 GitHub: Flcookie

🧠 Focus: LLM Engineering, Agentic AI, LangGraph, Streamlit Apps