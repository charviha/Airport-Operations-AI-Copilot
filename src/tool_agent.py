import os
import json

from dotenv import load_dotenv
from google import genai

from src.tools import (
    get_airport_metrics,
    calculate_driver_incentive,
    trigger_surge_override,
)

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

LLM_MODEL = "gemini-3.6-flash"


# =========================================================
# TOOL DEFINITIONS
# =========================================================

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "name": "get_airport_metrics",
        "description": (
            "Get the latest or timestamp-specific operational metrics "
            "for an airport. Use this when the user asks about airport "
            "performance, queue size, ETA, completion rate, active "
            "drivers, driver cancellations, surge multiplier, or "
            "request volume."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "airport": {
                    "type": "string",
                    "description": (
                        "Airport code such as SFO, LAX, or JFK."
                    ),
                },
                "timestamp": {
                    "type": "string",
                    "description": (
                        "Optional timestamp in format "
                        "YYYY-MM-DD HH:MM:SS."
                    ),
                },
            },
            "required": ["airport"],
        },
    },
    {
        "type": "function",
        "name": "calculate_driver_incentive",
        "description": (
            "Calculate the recommended driver incentive based on "
            "airport queue size and active drivers."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "airport": {
                    "type": "string",
                    "description": (
                        "Airport code such as SFO, LAX, or JFK."
                    ),
                },
                "queue_size": {
                    "type": "integer",
                    "description": "Current airport queue size.",
                },
                "active_drivers": {
                    "type": "integer",
                    "description": "Number of active drivers.",
                },
            },
            "required": [
                "airport",
                "queue_size",
                "active_drivers",
            ],
        },
    },
    {
        "type": "function",
        "name": "trigger_surge_override",
        "description": (
            "Request a surge multiplier override for an airport. "
            "Use this when the user explicitly asks to change or "
            "apply a surge multiplier."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "airport": {
                    "type": "string",
                    "description": (
                        "Airport code such as SFO, LAX, or JFK."
                    ),
                },
                "requested_multiplier": {
                    "type": "number",
                    "description": "Requested surge multiplier.",
                },
                "approved_by": {
                    "type": "string",
                    "description": (
                        "Name or role of the person who approved "
                        "the override, if approval has already "
                        "been granted."
                    ),
                },
            },
            "required": [
                "airport",
                "requested_multiplier",
            ],
        },
    },
]


# =========================================================
# TOOL EXECUTION
# =========================================================

def execute_tool(tool_name: str, arguments: dict) -> dict:

    try:

        if tool_name == "get_airport_metrics":

            return get_airport_metrics(**arguments)

        elif tool_name == "calculate_driver_incentive":

            return calculate_driver_incentive(**arguments)

        elif tool_name == "trigger_surge_override":

            return trigger_surge_override(**arguments)

        else:

            return {
                "success": False,
                "error": f"Unknown tool: {tool_name}",
            }

    except Exception as error:

        return {
            "success": False,
            "error": str(error),
        }


# =========================================================
# AIRPORT OPERATIONS AGENT
# =========================================================

def ask_agent(question: str) -> dict:

    system_instruction = """
You are an Airport Operations AI Copilot.

Your job is to answer airport operations questions using
the available operational tools.

Rules:

1. Use get_airport_metrics when the user asks about
   airport operational metrics.

2. Use calculate_driver_incentive when the user asks
   about driver incentives and provides queue size
   and active driver information.

3. Use trigger_surge_override when the user explicitly
   asks to change or apply a surge multiplier.

4. Never invent operational metrics.

5. Never claim a surge override was approved unless
   the tool explicitly confirms approval.

6. If a tool returns an error, explain the error clearly.

7. After receiving a tool result, summarize the result
   clearly for the airport operations user.

8. Keep answers concise but include important
   operational numbers.
    """

    # =====================================================
    # FIRST GEMINI REQUEST
    # =====================================================

    interaction = client.interactions.create(
        model=LLM_MODEL,
        input=question,
        system_instruction=system_instruction,
        tools=TOOL_DEFINITIONS,
        store=True,
    )

    # =====================================================
    # FIND FUNCTION CALLS
    # =====================================================

    tool_calls = []

    for step in interaction.steps:

        if getattr(step, "type", None) == "function_call":

            tool_calls.append(step)

    # =====================================================
    # NO TOOL REQUIRED
    # =====================================================

    if not tool_calls:

        return {
            "answer": interaction.output_text,
            "tool_calls": [],
        }

    # =====================================================
    # EXECUTE TOOL CALLS
    # =====================================================

    function_results = []
    tool_log = []

    for tool_call in tool_calls:

        tool_name = tool_call.name

        arguments = tool_call.arguments

        if isinstance(arguments, str):

            arguments = json.loads(arguments)

        print()
        print("TOOL CALLED")
        print("=" * 60)
        print("Tool:", tool_name)
        print("Arguments:", arguments)

        result = execute_tool(
            tool_name,
            arguments,
        )

        print("Result:", result)

        tool_log.append(
            {
                "tool_name": tool_name,
                "arguments": arguments,
                "result": result,
            }
        )

        # =================================================
        # FUNCTION RESULT
        # =================================================

        function_results.append(
            {
                "type": "function_result",
                "name": tool_name,
                "call_id": tool_call.id,
                "result": [
                    {
                        "type": "text",
                        "text": json.dumps(result),
                    }
                ],
            }
        )

    # =====================================================
    # SEND TOOL RESULTS BACK TO GEMINI
    # =====================================================

    final_interaction = client.interactions.create(
        model=LLM_MODEL,
        previous_interaction_id=interaction.id,
        tools=TOOL_DEFINITIONS,
        input=function_results,
        store=True,
    )

    return {
        "answer": final_interaction.output_text,
        "tool_calls": tool_log,
    }


# =========================================================
# TESTS
# =========================================================

if __name__ == "__main__":

    questions = "What are the latest operational metrics at SFO?"


    for question in questions:

        print()
        print("=" * 70)
        print("USER QUESTION")
        print("=" * 70)
        print(question)

        try:

            result = ask_agent(question)

            print()
            print("FINAL ANSWER")
            print("=" * 70)
            print(result["answer"])

        except Exception as error:

            print()
            print("ERROR")
            print("=" * 70)
            print(error)