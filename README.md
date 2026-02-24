# 🦈 Shark Tank AI: The Elite AI Pitch Arena

Welcome to **Shark Tank AI**, a high-stakes, real-time voice AI experience where you pitch your business ideas to a panel of legendary (and notoriously tough) AI Sharks. Built with **LiveKit Agents**, this project brings the boardroom to the browser with ultra-low latency and distinct AI personalities.

---

## 🚀 Key Features

- **The Sharks**: Pitch to Mark Cuban, Kevin O'Leary (Mr. Wonderful), and lori Greiner—each with their authentic personalities, voices, and investment criteria.
- **Ultra-Low Latency**: Powered by LiveKit's Realtime Media transport, enabling fluid, natural conversations.
- **Premium Interface**: A sleek, dark-mode dashboard built with React, Tailwind CSS, and Lucide-react.
- **Automatic Dispatching**: Seamlessly joins the room as soon as you connect, thanks to LiveKit's automated agent dispatching system.

---

## 🛠 Tech Stack

- **Backend**: Python with [LiveKit Agents SDK](https://docs.livekit.io/agents/), FastAPI for token generation, and `uv` for package management.
- **Frontend**: React, Vite, Tailwind CSS, and [LiveKit Components](https://docs.livekit.io/components/react/).
- **AI Engine**: Google Gemini Realtime Model for multi-modal, low-latency voice interaction.

---

## ⚡ LiveKit Implementation Details

This project leverages several advanced LiveKit features to provide a seamless "Shark Tank" experience:

### 1. Custom Token Endpoint

Implemented a FastAPI-based token server in `backend/api.py`. It securely handles LiveKit JWT generation, allowing the frontend to connect without exposing API secrets.

### 2. Automatic Agent Dispatch

We utilize LiveKit's dispatch system **without specifying an `agent_name`**. This ensures that as soon as a user enters a unique room, the Shark Agent(s) are automatically summoned to evaluate the pitch, providing a zero-friction experience.

### 3. LiveKit Cloud Deployment

- **Deployment**: Use `lk agent create` to create an agent and `lk agent deploy` to push your agents to the cloud.
- **Multiple Agents**: LiveKit Cloud's free tier supports 1 concurrent agent. For concurrent Mark, Kevin, and Lori presence, you can upgrade to a pro/self-hosted plan.
- **Secrets Management**: Sensitive keys (like `GOOGLE_API_KEY`) are managed via the LiveKit CLI:

  ```bash
  lk agent update-secrets --secrets GOOGLE_API_KEY=YOUR_KEY
  ```

---

## 🏃‍♂️ Getting Started

### Prerequisites

- [LiveKit CLI](https://docs.livekit.io/home/cli/)
- [uv](https://github.com/astral-sh/uv) (Python package manager)
- [Node.js](https://nodejs.org/)

### 1. Environment Setup

Create a `.env` file in the `backend/` directory:

```env
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret
GOOGLE_API_KEY=your-google-api-key
```

### 2. Run the Backend (API + Agent)

```bash
# Start the Token Server
uv run uvicorn backend.api:app --reload --port 8000

# Run an agent locally (e.g., Mark)
uv run backend/agents/mark.py dev
```

### 3. Run the Frontend

```bash
cd frontend
npm install
npm run dev
```

---

## 🚢 Deployment

The project includes a `Dockerfile` and `livekit.toml` generated for easy deployment.

- **Dockerfile**: Optimized minimal container using `uv`.
- **livekit.toml**: Tracking for your Cloud Agent IDs and subdomains.

Pitch your way to a deal. Good luck!
