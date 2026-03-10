# 🦈 Shark Tank AI: The Elite AI Pitch Arena

**Shark Tank AI** is a real-time voice experience where founders pitch to a rotating AI panel of Mark, Kevin, and Lori. The app uses LiveKit + Google realtime models for low-latency conversation and a turn-based panel flow.

1. Join a room
<img width="1424" height="897" alt="image" src="https://github.com/user-attachments/assets/fa4b12b1-6061-4d03-bc1f-b4daa704ef83" />
2. Pitch.
<img width="1440" height="782" alt="image" src="https://github.com/user-attachments/assets/d272807f-20d5-4010-ad3b-1a1ee0404138" />

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

Create `backend/.env` (you can copy from `backend/.env.example`):

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

Create `frontend/.env.local` (you can copy from `frontend/.env.example`):

```env
VITE_BACKEND_URL=http://localhost:8000
VITE_ACCESS_PASSWORD=your-access-password
```

```bash
npm install --prefix frontend
npm run dev --prefix frontend
```

### 5) Deploy backend with Docker + reverse proxy (custom server)

This repo includes:

- `backend/Dockerfile` for FastAPI backend
- `docker-compose.backend.yml` for backend + Caddy reverse proxy
- `Caddyfile` for routing and automatic TLS (Let's Encrypt)

1. On your server, clone/pull this repo.
2. Create `backend/.env` with production secrets (copy from `backend/.env.example`).
3. Start services:

```bash
sudo BACKEND_DOMAIN=api.example.com docker compose -f docker-compose.backend.yml up -d --build
```

4. Check status/logs:

```bash
sudo docker compose -f docker-compose.backend.yml ps
sudo docker compose -f docker-compose.backend.yml logs -f
```

5. Verify API:

```bash
curl -I https://api.example.com/docs
```

Notes:

- `shark-tank-caddy` is the only public entrypoint (`80/443`).
- `shark-tank-backend` is internal-only (`expose: 8000`).
- For your own domain later, point DNS to server IP and set `BACKEND_DOMAIN=api.yourdomain.com`.
- Caddy renews certificates automatically.

### 6) Frontend (Vercel) env

In Vercel, set:

```env
VITE_BACKEND_URL=https://api.example.com
VITE_ACCESS_PASSWORD=your-access-password
```

Then redeploy the frontend.

---

## ✅ Testing / Quality

```bash
uv run pytest
uv run ruff format backend/ tests/
uv run ruff check backend/ tests/
```

---

Pitch your way to a deal. Good luck.
