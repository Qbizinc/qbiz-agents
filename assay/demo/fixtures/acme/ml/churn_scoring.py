"""Acme's churn-explanation script — fixture file, parsed by AST only, never executed.

Deliberate smells: direct, ungoverned OpenAI usage with a hardcoded (fake) API key.
No cost cap, no loop bound, no audit trail.
"""

import openai

api_key = "sk-proj-EXAMPLE0000EXAMPLE0000EXAMPLE"


def explain_churn(customer_record: dict) -> str:
    client = openai.OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Explain why this customer might churn."},
            {"role": "user", "content": str(customer_record)},
        ],
    )
    return response.choices[0].message.content or ""
