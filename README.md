# JarvisAI

A **personal AI assistant** with an Iron Man–style Jarvis UX: HUD dashboard, voice wake word (“Hey Jarvis”), chat, reminders, and daily briefs. Built with FastAPI, Groq LLM, RAG (FAISS), and optional TTS/STT.

---

## Project overview

**JarvisAI** is a full-stack assistant that gives you:

- **Jarvis-style UI** — Central AI orb (idle / listening / processing / error), live status strip (mode, wake word, latency, date/time, network), conversation panel with confidence, intent/reasoning and task panels, proactive suggestions, and optional dev overlay.
- **Chat** — **General** mode (Groq + LangChain, FAISS RAG, learning from `database/learning_data/*.txt`) and **Realtime** mode (Tavily search + LLM). Popup chat (floating **J** button) so the main screen stays the dashboard.
- **Voice** — Say **“Hey Jarvis”** to wake; then speak your question. Offline **speech-to-text** via Whisper tiny (faster-whisper, no OpenAI API key). Optional reminder TTS (Murf).
- **Reminders** — Set by chat (“remind me in 30 minutes to…”) or API; in-process worker creates notifications and optional webhook. **Daily brief** includes **upcoming reminders** only and a **“What happened today”** section (reminders that already fired).
- **Daily brief** — Weather (OpenWeatherMap), headlines (Tavily), upcoming reminders, “What happened today” (sent reminders), time. Optional voice brief (Murf TTS). Generated on first request or at a scheduled hour.
- **Auth & data** — JWT auth; MySQL for users; chats, reminders, notifications, and briefs are **per-user**. Admin dashboard (Flask) for status, usage, alerts, and brief.

**Architecture:** Layered (API → Service → Repository), Pydantic Settings. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Quick start

```bash
# 1. Dependencies
pip install -r requirements.txt

# 2. Config
cp .env.example .env
# Edit .env: GROQ_API_KEYS (or GROQ_API_KEY), MySQL, JWT_SECRET, optional TAVILY, OPENWEATHERMAP, MURF

# 3. Run API (port 8000)
python run.py
```

Open **http://127.0.0.1:8000** → register/login → use the dashboard and popup chat. For admin stats and alerts: `python run_dashboard.py` → **http://127.0.0.1:5000**.

---

## Project structure

```
JarvisAI/
├── app/
│   ├── main.py              # FastAPI app, auth, chat, voice, reminders, brief
│   ├── models.py            # Pydantic request/response models
│   ├── auth.py              # JWT, password hashing
│   ├── db.py                # MySQL: users, reminders, notifications, daily_briefs
│   ├── deps.py
│   ├── services/
│   │   ├── chat_service.py  # Session & conversation, RAG
│   │   ├── groq_service.py  # Groq LLM (multi-key rotation)
│   │   ├── realtime_service.py  # Tavily + LLM
│   │   ├── brief_service.py # Daily brief (weather, reminders, headlines)
│   │   └── vector_store.py  # FAISS + embeddings
│   └── utils/
│       ├── whisper_stt.py   # Offline STT (faster-whisper, tiny)
│       ├── weather.py       # OpenWeatherMap
│       ├── murf_tts.py      # Murf TTS (brief + reminder voice)
│       ├── reminder_worker.py
│       ├── reminder_parser.py
│       └── time_info.py
├── static/
│   ├── index.html           # Jarvis UI (HUD, orb, status strip, chat popup)
│   └── app.js               # Dashboard, chat, voice (Hey Jarvis), reminders
├── dashboard/                # Flask admin (usage, alerts, brief)
├── database/
│   ├── learning_data/       # .txt files = RAG context
│   ├── chats_data/           # Chat sessions (.json)
│   └── vector_store/        # FAISS index
├── config.py                 # Settings from .env
├── run.py                    # Uvicorn (API on 8000)
├── run_dashboard.py          # Flask admin on 5000
├── requirements.txt
└── README.md
```

---

## Setup

1. **Python 3.10+**, virtualenv recommended:
   ```bash
   python -m venv venv
   venv\Scripts\activate   # Windows
   # source venv/bin/activate  # Linux/macOS
   pip install -r requirements.txt
   ```

2. **MySQL** — Create a DB (e.g. `jarvisai`). The app creates `users`, `reminders`, `notifications`, `daily_briefs`, etc. on startup.

3. **`.env`** (copy from `.env.example`):

   | Variable | Description |
   |----------|-------------|
   | `GROQ_API_KEYS` or `GROQ_API_KEY` | [Groq](https://console.groq.com) key(s), comma-separated |
   | `TAVILY_API_KEY` | [Tavily](https://tavily.com) (realtime search) |
   | `OPENWEATHERMAP_API_KEY` | [OpenWeatherMap](https://openweathermap.org/api) (weather in brief & chat) |
   | `OPENWEATHERMAP_DEFAULT_CITY` | Default city (e.g. `Delhi`) |
   | `MYSQL_*` | Host, port, user, password, database |
   | `JWT_SECRET` | Long random string for tokens |
   | `MURF_API_KEY` | [Murf](https://murf.ai/api) (brief + reminder voice) |
   | `ADMIN_EMAILS` | Comma-separated emails for admin dashboard |
   | `DEFAULT_ADMIN_EMAIL` | Email for seeded admin (dashboard login + scheduled brief). Set in .env only. |
   | `DEFAULT_ADMIN_PASSWORD` | Password for seeded admin. Set in .env only. |
   | `RATE_LIMIT_CHAT` | e.g. `30/minute` |
   | `LOG_FILE` | e.g. `logs/jarvisai.log` |
   | `BRIEF_HOUR` | Hour (0–23) to generate daily brief; default 7 |

4. **Voice (Hey Jarvis)** — No API key needed for STT (Whisper tiny, local). For best compatibility with browser WebM, install **ffmpeg** on PATH (optional; PyAV is used first).

5. **Learning data** — Add `.txt` files under `database/learning_data/`; the general chat uses them as RAG context.

---

## Run

- **API + Jarvis UI:** `python run.py` → **http://127.0.0.1:8000**  
  Register/login, use the dashboard and the **J** button to open chat. Enable **Voice** in the chat input to use “Hey Jarvis” and speak your query.

- **Admin dashboard:** `python run_dashboard.py` → **http://127.0.0.1:5000**  
  Overview, status, usage, activity, alerts, daily brief (with optional voice).

- **Tests:** `pytest` (unit + integration; MySQL required for DB-dependent checks).

---

## API summary

**Auth:** `POST /auth/register`, `POST /auth/login` → JWT.

**Chat (Bearer token):**  
`POST /chat/general`, `POST /chat/realtime`, `GET /chats/sessions`, `GET /chats/sessions/{id}`.

**Voice (Bearer token):**  
`POST /voice/transcribe` — multipart `audio` (webm/wav) → `{ text, language, woke }`. “Hey Jarvis” sets `woke: true`.

**Reminders & brief (Bearer token):**  
`POST /reminders`, `GET /reminders`, `GET /notifications`, `GET /brief`, `GET /brief/audio`, `GET /notifications/audio/{id}`.

**Health:** `GET /health`, `GET /health/live`, `GET /health/ready`.

**Admin (admin user):** `GET /admin/status`, `GET /admin/usage`, `GET /admin/requests`.

---

## Daily brief

- **Content:** Weather (if `OPENWEATHERMAP_API_KEY` set), headlines (Tavily), **upcoming reminders only**, **“What happened today”** (reminders that already fired today), time.
- **Weather:** If the key is not set, the brief does not mention weather or suggest external sources.
- **Voice:** If `MURF_API_KEY` is set, the brief can be played as WAV via `GET /brief/audio`.

---

## Jarvis UI (overview)

- **Central orb** — Idle (blue), Listening (green), Processing (yellow), Speaking (waveform), Error (red).
- **Status strip** — Mode, wake word, response latency, date/time, network.
- **Conversation** — Popup with General/Realtime modes; confidence on replies.
- **Panels** — Intent & reasoning, active tasks, memory/context (collapsible).
- **Proactive suggestion** — One-time hint (e.g. daily brief).
- **Dev overlay** — `Ctrl+Shift+D` for token/model/tools placeholder.

---

## License

Use as per your project requirements.
