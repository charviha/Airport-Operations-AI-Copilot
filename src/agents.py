import os
import json

from dotenv import load_dotenv
from google import genai

from src.tools import (
    get_airport_metrics,
    calculate_driver_incentive,
    trigger_surge_override,
)

from src.rag import answer_question
from src.memory import ConversationMemory


load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

LLM_MODEL = "gemini-3.6-flash"

# Maximum number of reasoning/action cycles
MAX_ITERATIONS = 5


# ============================================================
# OPERATIONS INVESTIGATOR
# ============================================================

def operations_investigator(
    airport: str
) -> dict:

    """
    Investigates the current operational condition
    of an airport using telemetry data.
    """

    metrics = get_airport_metrics(airport)

    if not metrics.get("success"):
        return {
            "success": False,
            "agent": "Operations Investigator",
            "error": metrics.get("error")
        }

    queue = metrics["queue_size"]
    completion = metrics["completion_rate"]
    eta = metrics["avg_eta_minutes"]
    cancellation = metrics["driver_cancellation_rate"]

    issues = []

    if queue > 200:
        issues.append(
            "Queue is above the mandatory investigation threshold."
        )

    elif queue > 150:
        issues.append(
            "Queue is above the elevated congestion threshold."
        )

    if completion < 0.75:
        issues.append(
            "Completion rate is critically low."
        )

    if eta > 20:
        issues.append(
            "Average ETA is severely elevated."
        )

    if cancellation > 0.15:
        issues.append(
            "Driver cancellation rate is elevated."
        )

    return {
        "success": True,
        "agent": "Operations Investigator",
        "airport": airport.upper(),
        "metrics": metrics,
        "issues": issues,
    }


# ============================================================
# POLICY & COMPLIANCE AGENT
# ============================================================

def policy_compliance_agent(
    question: str,
    airport: str | None = None
) -> dict:

    """
    Uses the RAG pipeline to retrieve and answer
    policy-related questions.
    """

    result = answer_question(
        question,
        airport=airport,
        top_k=3
    )

    return {
        "success": True,
        "agent": "Policy & Compliance",
        "answer": result["answer"],
        "sources": result["sources"],
    }


# ============================================================
# RESOLUTION AGENT
# ============================================================

def resolution_agent(
    question: str,
    operations_result: dict | None,
    policy_result: dict | None
) -> dict:

    """
    Combines operational findings and policy information
    and produces a recommended resolution.
    """

    operations_text = json.dumps(
        operations_result or {},
        indent=2
    )

    policy_text = json.dumps(
        policy_result or {},
        indent=2
    )

    prompt = f"""
You are the Resolution Agent in an Airport Operations AI Copilot.

User Question:
{question}

Operations Investigator Result:
{operations_text}

Policy & Compliance Result:
{policy_text}

Your responsibilities:

1. Identify the operational issue.
2. Summarize the relevant metrics.
3. Identify applicable policy constraints.
4. Suggest practical next steps.
5. Never invent policy rules.
6. Never claim that an operational action was executed.
7. If an action requires human approval, clearly state that.
8. Separate facts from recommendations.
9. Keep the final response concise and professional.

Return a clear operational recommendation.
"""

    interaction = client.interactions.create(
        model=LLM_MODEL,
        input=prompt
    )

    return {
        "success": True,
        "agent": "Resolution Agent",
        "answer": interaction.output_text,
    }


# ============================================================
# ORCHESTRATOR
# ============================================================

class AirportOrchestrator:

    def __init__(self):

        self.memory = ConversationMemory()

    # --------------------------------------------------------
    # Determine which agents are required
    # --------------------------------------------------------

    def determine_agents(
        self,
        question: str
    ) -> list[str]:

        question_lower = question.lower()

        agents = []

        operational_keywords = [
            "metric",
            "metrics",
            "queue",
            "eta",
            "completion",
            "cancellation",
            "drivers",
            "requests",
            "operational",
            "current",
            "latest"
        ]

        policy_keywords = [
            "policy",
            "allowed",
            "maximum",
            "approval",
            "rule",
            "limit",
            "compliance",
            "threshold"
        ]

        resolution_keywords = [
            "what should",
            "recommend",
            "resolve",
            "fix",
            "action",
            "increase surge",
            "apply surge",
            "what can we do"
        ]

        if any(
            keyword in question_lower
            for keyword in operational_keywords
        ):
            agents.append("operations")

        if any(
            keyword in question_lower
            for keyword in policy_keywords
        ):
            agents.append("policy")

        if any(
            keyword in question_lower
            for keyword in resolution_keywords
        ):
            agents.append("resolution")

        # If nothing matched, use Policy & Compliance
        if not agents:
            agents.append("policy")

        # Resolution questions need both operations and policy
        if "resolution" in agents:

            if "operations" not in agents:
                agents.insert(0, "operations")

            if "policy" not in agents:
                agents.insert(1, "policy")

        # Remove duplicates while preserving order
        agents = list(dict.fromkeys(agents))

        return agents

    # --------------------------------------------------------
    # Main workflow
    # --------------------------------------------------------

    def run(
        self,
        question: str,
        airport: str | None = None,
        session_id: str = "default"
    ) -> dict:

        # ----------------------------------------------------
        # Save user message
        # ----------------------------------------------------

        self.memory.add_message(
            session_id,
            "user",
            question
        )

        history = self.memory.format_history(
            session_id
        )

        print("\n" + "=" * 70)
        print("ORCHESTRATOR")
        print("=" * 70)

        print("Question:", question)
        print("Airport:", airport)

        print("\nConversation Memory:")
        print(history)

        # ----------------------------------------------------
        # Determine agents
        # ----------------------------------------------------

        selected_agents = self.determine_agents(
            question
        )

        print("\nSelected Agents:")

        for agent in selected_agents:
            print(f"- {agent}")

        operations_result = None
        policy_result = None
        resolution_result = None

        # ----------------------------------------------------
        # ReAct-style workflow
        # ----------------------------------------------------

        iteration = 0

        # ====================================================
        # OPERATIONS AGENT
        # ====================================================

        if "operations" in selected_agents:

            iteration += 1

            print(
                f"\nIteration {iteration}/{MAX_ITERATIONS}"
            )

            if not airport:

                operations_result = {
                    "success": False,
                    "error": "Airport is required."
                }

            else:

                print(
                    "\n[Operations Investigator]"
                )

                operations_result = (
                    operations_investigator(
                        airport
                    )
                )

        # ====================================================
        # POLICY AGENT
        # ====================================================

        if "policy" in selected_agents:

            iteration += 1

            print(
                f"\nIteration {iteration}/{MAX_ITERATIONS}"
            )

            print(
                "\n[Policy & Compliance]"
            )

            policy_result = (
                policy_compliance_agent(
                    question,
                    airport
                )
            )

        # ====================================================
        # RESOLUTION AGENT
        # ====================================================

        if "resolution" in selected_agents:

            iteration += 1

            print(
                f"\nIteration {iteration}/{MAX_ITERATIONS}"
            )

            print(
                "\n[Resolution Agent]"
            )

            resolution_result = resolution_agent(
                question,
                operations_result,
                policy_result
            )

        # ----------------------------------------------------
        # Create final answer
        # ----------------------------------------------------

        if resolution_result:

            final_answer = resolution_result["answer"]

        elif policy_result:

            final_answer = policy_result["answer"]

        elif operations_result:

            if operations_result.get("success"):

                final_answer = (
                    "Operational findings for "
                    f"{operations_result['airport']}:\n"
                    + json.dumps(
                        operations_result["metrics"],
                        indent=2
                    )
                )

            else:

                final_answer = (
                    "Unable to retrieve operational metrics: "
                    + operations_result.get(
                        "error",
                        "Unknown error"
                    )
                )

        else:

            final_answer = (
                "I could not determine the appropriate "
                "agent for this request."
            )

        # ----------------------------------------------------
        # Save assistant response to memory
        # ----------------------------------------------------

        self.memory.add_message(
            session_id,
            "assistant",
            final_answer
        )

        # ----------------------------------------------------
        # Return complete execution trace
        # ----------------------------------------------------

        return {
            "question": question,
            "airport": airport,
            "selected_agents": selected_agents,
            "iterations": iteration,
            "operations": operations_result,
            "policy": policy_result,
            "resolution": resolution_result,
            "answer": final_answer,
            "memory": self.memory.get_history(
                session_id
            ),
        }


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    orchestrator = AirportOrchestrator()

    question = (
        "SFO queue is high. "
        "What should we do?"
    )

    result = orchestrator.run(
        question=question,
        airport="SFO",
        session_id="demo"
    )

    print("\n" + "=" * 70)
    print("FINAL RESPONSE")
    print("=" * 70)

    print(result["answer"])

    print("\n" + "=" * 70)
    print("EXECUTION TRACE")
    print("=" * 70)

    print(
        "Selected Agents:",
        result["selected_agents"]
    )

    print(
        "Iterations:",
        result["iterations"]
    )