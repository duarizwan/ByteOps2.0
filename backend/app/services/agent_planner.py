"""Small deterministic planner for ByteOps agent runs."""


def build_agent_plan(user_message: str, intent: str, connected_tools: list[str]) -> dict:
    required_tools = [] if intent in {"general", "workflow"} else [intent]
    missing_tools = [tool for tool in required_tools if tool not in connected_tools]
    blocked = bool(missing_tools)

    if intent == "general":
        steps = ["Answer directly", "Verify answer addresses the request"]
    elif intent == "workflow":
        steps = [
            "Extract workflow trigger and actions",
            "Create workflow record",
            "Verify workflow appears in the Workflows tab",
        ]
    else:
        steps = [
            f"Route to {intent} specialist",
            f"Execute requested {intent} work",
            "Verify answer addresses the request",
        ]

    return {
        "summary": user_message.strip()[:160],
        "intent": intent,
        "requires_tools": required_tools,
        "steps": steps,
        "blocked": blocked,
        "block_reason": f"{missing_tools[0]} is not connected" if missing_tools else None,
    }
