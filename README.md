# WhatsApp Message Scheduler

Tkinter desktop app to schedule WhatsApp messages via Twilio and manage contacts (SQLite).

## Structure
```
FrontEnd/   gui.py            Tkinter interface (run this)
BackEnd/    AutomatedMsg.py   Twilio WhatsApp sender
Database/   database.py       SQLite contacts (contacts.db is created on first run)
```

## Setup
```
pip install -r requirements.txt
cp .env.example .env      # then fill in your Twilio credentials
python FrontEnd/gui.py
```
