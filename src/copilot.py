#!/usr/bin/env python3
"""
UK Property Market Copilot – AI-powered Q&A and analytics.

Supports both CLI and import by webapp.
"""

import json
import os
import sqlite3
import sys
from typing import Any

from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

from .db import DB_PATH, get_db, schema_summary

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))

# ── System prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = f"""You are the UK Property Market Copilot, an expert AI analyst for residential property data sourced from HM Land Registry (England and Wales).

{schema_summary()}

BEHAVIOUR:
1. Use the `run_sql` tool to answer questions — never guess figures.
2. Always use the `property_analytics` view for query accuracy.
3. Match county/town using UPPER() or LIKE '%X%' since values are uppercase.
4. For broad queries (>10k results) summarise aggregates rather than listing rows.
5. Format prices as £NNN,NNN. Format counts with commas.
6. At the end of every answer, append an **Evidence** section showing the SQL used and row count returned.
7. Clarify if a question falls outside England & Wales (Scotland and Northern Ireland are not covered).
8. Be honest about data limitations: very recent months may be incomplete due to registration lag.

EXAMPLE QUESTIONS YOU CAN ANSWER:
- What is the average price of a detached house in Surrey in 2024?
- How many new-build flats were sold in Manchester last year?
- Show me the top 10 most expensive counties by median price in 2023.
- What percentage of sales in London are leasehold vs freehold?
- Has the average price in Bristol gone up or down since 2010?
- How many properties sold for over £1 million in 2024?
"""


# ── Tool definition ──────────────────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_sql",
            "description": (
                "Execute a read-only SQL query against the UK property SQLite database. "
                "Returns rows as a list of dicts. Limit results to 50 rows max for display."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "The SQL SELECT statement to run.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max rows to return (default 20, max 100).",
                        "default": 20,
                    },
                },
                "required": ["sql"],
            },
        },
    }
]


# ── Tool execution ───────────────────────────────────────────────────────────

def run_sql(sql: str, limit: int = 20, db_path: str = DB_PATH) -> dict[str, Any]:
    """Execute SQL and return rows + metadata."""
    # Safety: only allow SELECT
    stripped = sql.strip().upper()
    if not stripped.startswith("SELECT") and not stripped.startswith("WITH"):
        return {"error": "Only SELECT queries are permitted."}

    limit = min(int(limit), 100)
    # Inject LIMIT if not present
    if "LIMIT" not in stripped:
        sql = f"{sql.rstrip(';')} LIMIT {limit}"

    try:
        con = get_db(db_path)
        cur = con.execute(sql)
        rows = [dict(r) for r in cur.fetchall()]
        con.close()
        return {"rows": rows, "count": len(rows), "sql": sql}
    except sqlite3.Error as e:
        return {"error": str(e), "sql": sql}


# ── Chat completion loop ─────────────────────────────────────────────────────

def chat(
    messages: list[dict],
    db_path: str = DB_PATH,
    max_tool_rounds: int = 5,
) -> tuple[str, list[dict]]:
    """
    Run a multi-turn conversation with tool use.
    Returns (assistant_reply, updated_messages).
    """
    history = list(messages)

    for _ in range(max_tool_rounds):
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + history,
            tools=TOOLS,
            tool_choice="auto",
            max_tokens=2048,
        )
        msg = resp.choices[0].message

        # Append assistant message to history
        history.append(msg.model_dump(exclude_unset=True))

        if msg.tool_calls:
            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments)
                result = run_sql(
                    sql=args["sql"],
                    limit=args.get("limit", 20),
                    db_path=db_path,
                )
                history.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result),
                    }
                )
        else:
            # Final text response
            return msg.content or "", history

    return "I was unable to complete that analysis. Please try rephrasing.", history


# ── CLI entry point ──────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description="UK Property Market Copilot (CLI)")
    parser.add_argument("--db", default=DB_PATH, help="SQLite database path")
    args = parser.parse_args()

    print("UK Property Market Copilot")
    print("Data: HM Land Registry Price Paid Data (England & Wales)")
    print("Type 'exit' to quit.\n")

    messages: list[dict] = []
    while True:
        try:
            q = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break
        if not q or q.lower() in ("exit", "quit"):
            break
        messages.append({"role": "user", "content": q})
        reply, messages = chat(messages, db_path=args.db)
        print(f"\nCopilot: {reply}\n")


if __name__ == "__main__":
    main()
