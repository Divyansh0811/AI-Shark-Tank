def extract_messages(chat_ctx, start_idx: int = 0) -> str:
    """Format chat_ctx messages[start_idx:] into a labelled transcript block."""
    if chat_ctx is None:
        return ""
    messages_fn = getattr(chat_ctx, "messages", None)
    all_messages = messages_fn() if callable(messages_fn) else (messages_fn or [])
    messages = all_messages[start_idx:]
    lines = []
    for msg in messages:
        role = getattr(msg, "role", None)
        role_str = role.value if hasattr(role, "value") else str(role)
        if role_str == "system":
            continue
        content = getattr(msg, "content", "")
        if isinstance(content, list):
            text = " ".join(getattr(part, "text", str(part)) for part in content)
        else:
            text = str(content) if content else ""
        text = text.strip()
        if not text:
            continue
        label = "Entrepreneur" if role_str == "user" else "Shark"
        lines.append(f"  {label}: {text}")
    return "\n".join(lines)


def build_turn_summary(shark_name: str, chat_ctx, start_idx: int) -> str:
    """Compress a single shark's turn into a short labelled block."""
    body = extract_messages(chat_ctx, start_idx)
    if not body:
        return ""
    return f"[{shark_name}]\n{body}"


def build_shark_instructions(config: dict, turn_state) -> str:
    """Build system instructions with live context and compressed prior-turn summaries."""
    base = config["instructions"]
    live_notice = "You are LIVE right now on Shark Tank."
    if not turn_state.turn_summaries:
        return f"{live_notice} {base}"
    history = "\n\n".join(turn_state.turn_summaries)
    return (
        f"{live_notice} {base}\n\n"
        f"Pitch conversation so far (one block per shark turn):\n"
        f"---\n{history}\n---\n\n"
        f"You have been sitting on the panel listening to everything above. "
        f"Introduce yourself and probe an angle the previous sharks have not yet covered."
    )
