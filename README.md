# 🦈 Shark Tank AI: The Elite AI Pitch Arena

**Shark Tank AI** is a real-time voice experience where founders pitch to a rotating AI panel of Mark, Kevin, and Lori. The app uses LiveKit + Google realtime models for low-latency conversation and a turn-based panel flow.

---

## 🚀 Key Features

- **Three distinct Sharks** with unique personas and voices.
- **Turn-based panel orchestration** (one active shark session at a time, all sharks visible in room presence).
- **Live turn progression** with automatic handoff after each shark's exchange window.
- **Decision-oriented prompting**: sharks ask for required info, can finalize decisions, and may propose combined offers.
- **Frontend access gate** with password prompt to reduce accidental LLM spend.

---

## 🛠 Tech Stack

- **Backend**: FastAPI + LiveKit Agents SDK (Python), managed with `uv`.
- **Frontend**: React + Vite + Tailwind + LiveKit Components.
- **Model**: Google realtime model via LiveKit plugins.

---

## 🧱 Project Structure

```text
backend/
  api.py
  constants.py
  controllers/
  routers/
  schemas/
    shark.py
    turn.py
  services/
    shark_service.py      # SharkAgent
    turn_service.py       # turn state + advancing turns
    livekit_service.py    # room connections + join orchestration
  utils/
    shark_utils.py        # turn summaries + instruction builder
    turn_utils.py         # room name resolution
    livekit_utils.py      # token + room helpers

frontend/
  src/
    App.tsx
```

## 🏃 Getting Started

### 1) Prerequisites

- Python + [`uv`](https://github.com/astral-sh/uv)
- Node.js + npm

### 2) Backend env

Create `backend/.env`:

```env
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret
GOOGLE_API_KEY=your-google-api-key
```

### 3) Run backend

```bash
uv run uvicorn backend.api:app --reload --port 8000
```

### 4) Run frontend

Create `frontend/.env.local`:

```env
VITE_ACCESS_PASSWORD=your-access-password
```

```bash
npm install --prefix frontend
npm run dev --prefix frontend
```

---

## ✅ Testing / Quality

```bash
uv run pytest
uv run ruff format backend/ tests/
uv run ruff check backend/ tests/
```

---

Pitch your way to a deal. Good luck.
