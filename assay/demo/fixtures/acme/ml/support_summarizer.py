"""Acme's support-ticket summarizer — fixture file, parsed by AST only, never executed.

Deliberate smell: ungoverned Anthropic usage (key from env, so no credential finding —
but still no cost cap, loop bound, or audit trail).
"""

import os

import anthropic


def summarize_ticket(ticket_text: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=500,
        messages=[{"role": "user", "content": f"Summarize this support ticket:\n{ticket_text}"}],
    )
    return message.content[0].text
