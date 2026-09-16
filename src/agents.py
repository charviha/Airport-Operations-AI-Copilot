
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

def operations_investigator(airport: str) -> dict:
    """
    Investigates the current operational condition
    of an airport using telemetry data.
    """

    metrics = get_airport_metrics(airport)

    if not metrics.get("success"):
        return {
            "success": False,
            "agent": "Operations Investigator",
            "error": metrics.get("error"),
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

    if not issues:
        issues.append(
            "No critical operational threshold has been breached."
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
    airport: str | None = None,
) -> dict:
    """
    Uses the RAG pipeline to retrieve and answer
    policy-related questions.
    """

    result = answer_question(
        question,
        airport=airport,
        top_k=3,
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
    policy_result: dict | None,
) -> dict:
    """
    Combines operational findings and policy information
    and produces a recommended resolution.
    """

    operations_text = json.dumps(
        operations_result or {},
        indent=2,
    )

    policy_text = json.dumps(
        policy_result or {},
        indent=2,
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
        input=prompt,
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
    # Determine initial agents
    # --------------------------------------------------------

    def determine_initial_agents(
        self,
        question: str,
    ) -> list[str]:
        """
        Determines the first agent that should investigate
        the user's request.

        The rest of the workflow is decided dynamically
        after agent results are observed.
        """

        question_lower = question.lower()

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
            "latest",
        ]

        policy_keywords = [
            "policy",
            "allowed",
            "maximum",
            "approval",
            "rule",
            "limit",
            "compliance",
            "threshold",
        ]

        resolution_keywords = [
            "what should",
            "recommend",
            "resolve",
            "fix",
            "action",
            "what can we do",
        ]

        # Resolution questions need operational
        # investigation first.
        if any(
            keyword in question_lower
            for keyword in resolution_keywords
        ):
            return ["operations"]

        if any(
            keyword in question_lower
            for keyword in operational_keywords
        ):
            return ["operations"]

        if any(
            keyword in question_lower
            for keyword in policy_keywords
        ):
            return ["policy"]

        # Default to policy/RAG.
        return ["policy"]

    # --------------------------------------------------------
    # Decide what to do after operations investigation
    # --------------------------------------------------------

    def decide_after_operations(
        self,
        question: str,
        operations_result: dict,
    ) -> str:
        """
        Determines the next step after operational
        investigation.

        Returns:
            policy
            resolution
            done
        """

        question_lower = question.lower()

        resolution_keywords = [
            "what should",
            "recommend",
            "resolve",
            "fix",
            "action",
            "what can we do",
            "increase",
            "decrease",
            "change",
            "override",
        ]

        policy_keywords = [
            "policy",
            "allowed",
            "maximum",
            "approval",
            "rule",
            "limit",
            "compliance",
            "threshold",
        ]

        # If the user explicitly wants a recommendation,
        # policy should be checked before resolution.
        if any(
            keyword in question_lower
            for keyword in resolution_keywords
        ):
            return "policy"

        # If the user is asking specifically about policy,
        # retrieve policy information.
        if any(
            keyword in question_lower
            for keyword in policy_keywords
        ):
            return "policy"

        # Pure metrics question is already answered.
        return "done"

    # --------------------------------------------------------
    # Decide what to do after policy investigation
    # --------------------------------------------------------

    def decide_after_policy(
        self,
        question: str,
    ) -> str:
        """
        Determines whether a resolution agent is required.
        """

        question_lower = question.lower()

        resolution_keywords = [
            "what should",
            "recommend",
            "resolve",
            "fix",
            "action",
            "what can we do",
            "increase",
            "decrease",
            "change",
            "override",
        ]

        if any(
            keyword in question_lower
            for keyword in resolution_keywords
        ):
            return "resolution"

        return "done"

    # --------------------------------------------------------
    # Main agentic workflow
    # --------------------------------------------------------

    def run(
        self,
        question: str,
        airport: str | None = None,
        session_id: str = "default",
    ) -> dict:

        # ----------------------------------------------------
        # Save user message
        # ----------------------------------------------------

        self.memory.add_message(
            session_id,
            "user",
            question,
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
        # Initial decision
        # ----------------------------------------------------

        pending_agents = self.determine_initial_agents(
            question
        )

        print("\nInitial Agent:")
        print("-", pending_agents[0])

        # ----------------------------------------------------
        # Results
        # ----------------------------------------------------

        operations_result = None
        policy_result = None
        resolution_result = None

        execution_trace = []

        iteration = 0

        # ----------------------------------------------------
        # Dynamic ReAct-style loop
        # ----------------------------------------------------

        while pending_agents and iteration < MAX_ITERATIONS:

            current_agent = pending_agents.pop(0)

            iteration += 1

            trace_entry = {
                "iteration": iteration,
                "agent": current_agent,
                "status": "started",
            }

            print(
                f"\nIteration {iteration}/{MAX_ITERATIONS}"
            )

            # ==================================================
            # OPERATIONS
            # ==================================================

            if current_agent == "operations":

                print("\n[Operations Investigator]")

                trace_entry["action"] = (
                    "Investigating airport telemetry."
                )

                if not airport:

                    operations_result = {
                        "success": False,
                        "agent": "Operations Investigator",
                        "error": "Airport is required.",
                    }

                else:

                    operations_result = (
                        operations_investigator(
                            airport
                        )
                    )

                trace_entry["result"] = operations_result
                trace_entry["status"] = "completed"

                execution_trace.append(trace_entry)

                # Decide next action based on result.
                next_action = self.decide_after_operations(
                    question,
                    operations_result,
                )

                print(
                    "Next decision:",
                    next_action,
                )

                if next_action == "policy":
                    pending_agents.append("policy")

            # ==================================================
            # POLICY
            # ==================================================

            elif current_agent == "policy":

                print("\n[Policy & Compliance]")

                trace_entry["action"] = (
                    "Retrieving relevant airport policy."
                )

                policy_result = (
                    policy_compliance_agent(
                        question,
                        airport,
                    )
                )

                trace_entry["result"] = policy_result
                trace_entry["status"] = "completed"

                execution_trace.append(trace_entry)

                # Decide whether resolution is required.
                next_action = self.decide_after_policy(
                    question
                )

                print(
                    "Next decision:",
                    next_action,
                )

                if next_action == "resolution":
                    pending_agents.append("resolution")

            # ==================================================
            # RESOLUTION
            # ==================================================

            elif current_agent == "resolution":

                print("\n[Resolution Agent]")

                trace_entry["action"] = (
                    "Combining operational findings "
                    "and policy constraints."
                )

                resolution_result = resolution_agent(
                    question,
                    operations_result,
                    policy_result,
                )

                trace_entry["result"] = resolution_result
                trace_entry["status"] = "completed"

                execution_trace.append(trace_entry)

                print(
                    "Resolution generated."
                )

        # ----------------------------------------------------
        # Iteration limit protection
        # ----------------------------------------------------

        if pending_agents:
            execution_trace.append({
                "iteration": iteration,
                "agent": "Orchestrator",
                "status": "stopped",
                "reason": (
                    "Maximum iteration limit reached."
                ),
            })

        # ----------------------------------------------------
        # Final answer
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
                        indent=2,
                    )
                )

            else:

                final_answer = (
                    "Unable to retrieve operational metrics: "
                    + operations_result.get(
                        "error",
                        "Unknown error",
                    )
                )

        else:

            final_answer = (
                "I could not determine the appropriate "
                "agent for this request."
            )

        # ----------------------------------------------------
        # Save assistant response
        # ----------------------------------------------------

        self.memory.add_message(
            session_id,
            "assistant",
            final_answer,
        )

        # ----------------------------------------------------
        # Complete execution trace
        # ----------------------------------------------------

        return {
            "question": question,
            "airport": airport,
            "selected_agents": [
                item["agent"]
                for item in execution_trace
                if item["agent"] != "Orchestrator"
            ],
            "iterations": iteration,
            "operations": operations_result,
            "policy": policy_result,
            "resolution": resolution_result,
            "execution_trace": execution_trace,
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
        session_id="demo",
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
        result["selected_agents"],
    )

    print(
        "Iterations:",
        result["iterations"],
    )

    for step in result["execution_trace"]:
        print(
            f"\nIteration {step.get('iteration')}"
            f" | Agent: {step.get('agent')}"
            f" | Status: {step.get('status')}"
        )
