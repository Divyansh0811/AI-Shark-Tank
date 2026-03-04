import asyncio

# How many entrepreneur messages each shark gets before passing to the next
MAX_EXCHANGES_PER_SHARK = 2

DEFAULT_AGENT_NAMES = ["Mark", "Kevin", "Lori"]

AGENT_CONFIGS = {
    "Mark": {
        "voice": "Puck",
        "temperature": 0.6,
        "instructions": (
            "You are Mark Cuban from Shark Tank. You are bold, tech-focused, and "
            "look for scalability."
        ),
    },
    "Kevin": {
        "voice": "Puck",
        "temperature": 0.6,
        "instructions": (
            "You are Kevin O'Leary from Shark Tank. You are cynical, focused on "
            "royalties and margins."
        ),
    },
    "Lori": {
        "voice": "Kore",
        "temperature": 0.8,
        "instructions": (
            "You are Lori Greiner from Shark Tank. Queen of QVC. You look for hero "
            "products with mass-market appeal."
        ),
    },
}

AGENT_JOIN_LOCK = asyncio.Lock()
