import os
import json
import re

from dotenv import load_dotenv
from google import genai

from src.tools import (
    get_airport_metrics,
    calculate_driver_incentive,
    trigger_surge_override,
)

from src.rag import answer_question
from src.memory import ConversationMemory

from src.guardrails import (
    run_guardrails,
    validate_action,
    request_human_approval,
    process_approval,
    create_audit_record,
)


load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

LLM_MODEL = "gemini-3.6-flash"

MAX_ITERATIONS = 5


# ============================================================
# OPERATIONS INVESTIGATOR
# ============================================================

def operations_investigator(airport: str) -> dict:

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
7. Do not bypass human approval.
8. Separate facts from recommendations.
9. Keep the final response concise and professional.

If a sensitive operational action is recommended,
describe it as a recommendation only.

The Guardrails layer controls whether the action
may actually be executed.

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
# ACTION EXTRACTION
# ============================================================

def extract_surge_request(
    question: str,
    airport: str | None,
) -> dict | None:

    question_lower = question.lower()

    surge_action_pattern = re.compile(
        r"\b("
        r"increase|"
        r"raise|"
        r"set|"
        r"change|"
        r"override|"
        r"trigger|"
        r"apply"
        r")\b"
        r".{0,50}"
        r"\bsurge\b",
        re.IGNORECASE,
    )

    if not surge_action_pattern.search(question_lower):
        return None

    airport_match = re.search(
        r"\b(SFO|LAX|JFK)\b",
        question,
        re.IGNORECASE,
    )

    if airport_match:
        detected_airport = (
            airport_match.group(1).upper()
        )
    elif airport:
        detected_airport = airport.upper()
    else:
        detected_airport = None

    if not detected_airport:
        return {
            "action": "trigger_surge_override",
            "airport": None,
            "requested_multiplier": None,
        }

    multiplier_match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*x\b",
        question_lower,
    )

    if not multiplier_match:
        return {
            "action": "trigger_surge_override",
            "airport": detected_airport,
            "requested_multiplier": None,
        }

    multiplier = float(
        multiplier_match.group(1)
    )

    return {
        "action": "trigger_surge_override",
        "airport": detected_airport,
        "requested_multiplier": multiplier,
    }


# ============================================================
# SURGE ACTION GUARDRAIL
# ============================================================

def handle_surge_action(
    question: str,
    airport: str,
    execution_trace: list[dict],
    approved_by: str | None = None,
    approval_decision: bool | None = None,
) -> dict:

    request = extract_surge_request(
        question,
        airport,
    )

    if not request:
        return {
            "action_detected": False,
        }

    # Use explicitly mentioned airport if available.
    target_airport = (
        request.get("airport")
        or airport
    )

    requested_multiplier = request[
        "requested_multiplier"
    ]

    if requested_multiplier is None:

        result = {
            "success": False,
            "action": "trigger_surge_override",
            "error": (
                "A surge multiplier is required. "
                "Example: increase SFO surge to 1.4x."
            ),
        }

        execution_trace.append({
            "iteration": len(execution_trace) + 1,
            "agent": "Guardrails",
            "status": "blocked",
            "action": "validate_surge_request",
            "result": result,
        })

        return {
            "action_detected": True,
            "executed": False,
            "result": result,
        }

    validation = validate_action(
        action="trigger_surge_override",
        airport=target_airport,
        requested_multiplier=requested_multiplier,
    )

    execution_trace.append({
        "iteration": len(execution_trace) + 1,
        "agent": "Guardrails",
        "status": (
            "validated"
            if validation.get("valid")
            else "blocked"
        ),
        "action": "validate_surge_request",
        "result": validation,
    })

    if not validation.get("valid"):

        return {
            "action_detected": True,
            "executed": False,
            "result": {
                "success": False,
                "message": "Action blocked by guardrails.",
                "validation": validation,
            },
        }

    if validation.get(
        "requires_human_approval"
    ):

        approval_request = request_human_approval(
            action="trigger_surge_override",
            airport=target_airport,
            details={
                "requested_multiplier":
                    requested_multiplier,
                "approval_threshold":
                    validation.get(
                        "approval_threshold"
                    ),
                "max_allowed":
                    validation.get(
                        "max_allowed"
                    ),
            },
        )

        execution_trace.append({
            "iteration": len(execution_trace) + 1,
            "agent": "Human-in-the-Loop",
            "status": "pending",
            "action": "request_human_approval",
            "result": approval_request,
        })

        # ----------------------------------------------------
        # No human decision yet
        # ----------------------------------------------------

        if approval_decision is None:

            audit = create_audit_record(
                question=question,
                airport=target_airport,
                risk_level="HIGH",
                action="trigger_surge_override",
                result={
                    "status": "PENDING_APPROVAL",
                    "requested_multiplier":
                        requested_multiplier,
                },
            )

            return {
                "action_detected": True,
                "executed": False,
                "approval_required": True,
                "approval_request": approval_request,
                "audit_record": audit,
                "result": {
                    "success": False,
                    "status": "PENDING_APPROVAL",
                    "message": (
                        "Human approval is required "
                        "before the surge override can "
                        "be executed."
                    ),
                },
            }

        # ----------------------------------------------------
        # Process human decision
        # ----------------------------------------------------

        approval_result = process_approval(
            approval_request,
            approved=approval_decision,
            approved_by=approved_by,
        )

        execution_trace.append({
            "iteration": len(execution_trace) + 1,
            "agent": "Human-in-the-Loop",
            "status": approval_result.get(
                "status",
                "error",
            ),
            "action": "process_approval",
            "result": approval_result,
        })

        if not approval_result.get(
            "approved",
            False,
        ):

            audit = create_audit_record(
                question=question,
                airport=target_airport,
                risk_level="HIGH",
                action="trigger_surge_override",
                result={
                    "status": "REJECTED",
                    "approval": approval_result,
                },
            )

            return {
                "action_detected": True,
                "executed": False,
                "approval_required": True,
                "approval_result": approval_result,
                "audit_record": audit,
                "result": {
                    "success": False,
                    "status": "REJECTED",
                    "message": (
                        "Human approval was rejected. "
                        "No operational action was executed."
                    ),
                },
            }

        # ----------------------------------------------------
        # APPROVED -> execute action
        # ----------------------------------------------------

        execution_result = trigger_surge_override(
            airport=target_airport,
            requested_multiplier=requested_multiplier,
            approved_by=approved_by,
        )

        execution_trace.append({
            "iteration": len(execution_trace) + 1,
            "agent": "Execution Tool",
            "status": (
                "completed"
                if execution_result.get("success")
                else "failed"
            ),
            "action": "trigger_surge_override",
            "result": execution_result,
        })

        audit = create_audit_record(
            question=question,
            airport=target_airport,
            risk_level="HIGH",
            action="trigger_surge_override",
            result={
                "approval": approval_result,
                "execution": execution_result,
            },
        )

        return {
            "action_detected": True,
            "executed": execution_result.get(
                "success",
                False,
            ),
            "approval_required": True,
            "approval_result": approval_result,
            "execution_result": execution_result,
            "audit_record": audit,
            "result": execution_result,
        }

    # --------------------------------------------------------
    # Standard-range action
    # --------------------------------------------------------

    execution_result = trigger_surge_override(
        airport=target_airport,
        requested_multiplier=requested_multiplier,
    )

    execution_trace.append({
        "iteration": len(execution_trace) + 1,
        "agent": "Execution Tool",
        "status": (
            "completed"
            if execution_result.get("success")
            else "failed"
        ),
        "action": "trigger_surge_override",
        "result": execution_result,
    })

    audit = create_audit_record(
        question=question,
        airport=target_airport,
        risk_level="MEDIUM",
        action="trigger_surge_override",
        result=execution_result,
    )

    return {
        "action_detected": True,
        "executed": execution_result.get(
            "success",
            False,
        ),
        "approval_required": False,
        "execution_result": execution_result,
        "audit_record": audit,
        "result": execution_result,
    }


# ============================================================
# ORCHESTRATOR
# ============================================================

class AirportOrchestrator:

    def __init__(self):

        self.memory = ConversationMemory()

    # --------------------------------------------------------
    # Initial agent selection
    # --------------------------------------------------------

    def determine_initial_agents(
        self,
        question: str,
    ) -> list[str]:

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
            "increase surge",
            "apply surge",
            "what can we do",
        ]

        agents = []

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

        if not agents:
            agents.append("policy")

        if "resolution" in agents:

            if "operations" not in agents:
                agents.insert(0, "operations")

            if "policy" not in agents:
                agents.insert(1, "policy")

        return list(
            dict.fromkeys(agents)
        )

    # --------------------------------------------------------
    # Decide next agent after operations
    # --------------------------------------------------------

    def decide_after_operations(
        self,
        question: str,
    ) -> str:

        question_lower = question.lower()

        if any(
            keyword in question_lower
            for keyword in [
                "policy",
                "allowed",
                "maximum",
                "approval",
                "limit",
                "threshold",
                "surge",
                "action",
                "increase",
            ]
        ):
            return "policy"

        if any(
            keyword in question_lower
            for keyword in [
                "what should",
                "recommend",
                "resolve",
                "fix",
                "what can we do",
            ]
        ):
            return "resolution"

        return "done"

    # --------------------------------------------------------
    # Decide next agent after policy
    # --------------------------------------------------------

    def decide_after_policy(
        self,
        question: str,
    ) -> str:

        question_lower = question.lower()

        if any(
            keyword in question_lower
            for keyword in [
                "what should",
                "recommend",
                "resolve",
                "fix",
                "action",
                "what can we do",
                "increase surge",
                "apply surge",
            ]
        ):
            return "resolution"

        return "done"

    # --------------------------------------------------------
    # Main workflow
    # --------------------------------------------------------

    def run(
        self,
        question: str,
        airport: str | None = None,
        session_id: str = "default",
        approved_by: str | None = None,
        approval_decision: bool | None = None,
    ) -> dict:

        # ----------------------------------------------------
        # Resolve airport from question or UI selection
        # ----------------------------------------------------

        detected_airport_match = re.search(
            r"\b(SFO|LAX|JFK)\b",
            question,
            re.IGNORECASE,
        )

        if detected_airport_match:

            effective_airport = (
                detected_airport_match.group(1).upper()
            )

        else:

            effective_airport = (
                airport.upper()
                if airport
                else None
            )

        airport = effective_airport

        # ----------------------------------------------------
        # Guardrails FIRST
        # ----------------------------------------------------

        guardrail_result = run_guardrails(
            question,
            airport,
        )

        print("\n" + "=" * 70)
        print("GUARDRAILS")
        print("=" * 70)

        print(
            "Risk Level:",
            guardrail_result.get(
                "risk_level"
            ),
        )

        print(
            "Human Approval Required:",
            guardrail_result.get(
                "requires_human_approval"
            ),
        )

        if not guardrail_result.get(
            "allowed",
            False,
        ):

            print(
                "Request blocked:",
                guardrail_result.get(
                    "error"
                ),
            )

            return {
                "question": question,
                "airport": airport,
                "answer": (
                    "Request blocked by guardrails: "
                    + guardrail_result.get(
                        "error",
                        "Invalid request.",
                    )
                ),
                "guardrails": guardrail_result,
                "execution_trace": [],
                "iterations": 0,
            }

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
        # Detect sensitive action
        # ----------------------------------------------------

        execution_trace = []

        surge_request = extract_surge_request(
            question,
            airport,
        )

        action_result = None

        if surge_request:

            action_result = handle_surge_action(
                question=question,
                airport=airport,
                execution_trace=execution_trace,
                approved_by=approved_by,
                approval_decision=approval_decision,
            )

            # Pending approval
            if (
                action_result.get(
                    "approval_required"
                )
                and not action_result.get(
                    "executed",
                    False,
                )
                and action_result.get(
                    "approval_result"
                ) is None
            ):

                final_answer = (
                    action_result["result"].get(
                        "message",
                        "Human approval is required.",
                    )
                )

                self.memory.add_message(
                    session_id,
                    "assistant",
                    final_answer,
                )

                return {
                    "question": question,
                    "airport": airport,
                    "answer": final_answer,
                    "guardrails": guardrail_result,
                    "action": action_result,
                    "execution_trace": execution_trace,
                    "iterations": len(
                        execution_trace
                    ),
                    "memory": self.memory.get_history(
                        session_id
                    ),
                }

            # Rejected approval
            if (
                action_result.get(
                    "approval_result",
                    {}
                ).get("status") == "REJECTED"
            ):

                final_answer = (
                    action_result["result"].get(
                        "message",
                        "Operational action rejected.",
                    )
                )

                self.memory.add_message(
                    session_id,
                    "assistant",
                    final_answer,
                )

                return {
                    "question": question,
                    "airport": airport,
                    "answer": final_answer,
                    "guardrails": guardrail_result,
                    "action": action_result,
                    "execution_trace": execution_trace,
                    "iterations": len(
                        execution_trace
                    ),
                    "memory": self.memory.get_history(
                        session_id
                    ),
                }

            # Invalid action
            if not action_result.get(
                "result",
                {}
            ).get(
                "success",
                False,
            ):

                final_answer = (
                    action_result["result"].get(
                        "message",
                        "Operational action blocked.",
                    )
                )

                self.memory.add_message(
                    session_id,
                    "assistant",
                    final_answer,
                )

                return {
                    "question": question,
                    "airport": airport,
                    "answer": final_answer,
                    "guardrails": guardrail_result,
                    "action": action_result,
                    "execution_trace": execution_trace,
                    "iterations": len(
                        execution_trace
                    ),
                    "memory": self.memory.get_history(
                        session_id
                    ),
                }

        # ----------------------------------------------------
        # Dynamic ReAct-style agent workflow
        # ----------------------------------------------------

        pending_agents = self.determine_initial_agents(
            question
        )

        selected_agents = []

        operations_result = None
        policy_result = None
        resolution_result = None

        iteration = 0

        print("\nInitial Agents:")

        for agent in pending_agents:
            print("-", agent)

        while (
            pending_agents
            and iteration < MAX_ITERATIONS
        ):

            agent = pending_agents.pop(0)

            if agent in selected_agents:
                continue

            iteration += 1
            selected_agents.append(agent)

            print(
                f"\nIteration {iteration}/{MAX_ITERATIONS}"
            )

            # =================================================
            # OPERATIONS
            # =================================================

            if agent == "operations":

                print(
                    "\n[Operations Investigator]"
                )

                if not airport:

                    operations_result = {
                        "success": False,
                        "agent":
                            "Operations Investigator",
                        "error":
                            "Airport is required.",
                    }

                else:

                    operations_result = (
                        operations_investigator(
                            airport
                        )
                    )

                execution_trace.append({
                    "iteration": iteration,
                    "agent":
                        "Operations Investigator",
                    "status":
                        (
                            "completed"
                            if operations_result.get(
                                "success"
                            )
                            else "failed"
                        ),
                    "action":
                        "get_airport_metrics",
                    "result":
                        operations_result,
                })

                next_agent = (
                    self.decide_after_operations(
                        question
                    )
                )

                print(
                    "Next decision:",
                    next_agent
                )

                if (
                    next_agent != "done"
                    and next_agent not in selected_agents
                    and next_agent not in pending_agents
                ):
                    pending_agents.append(
                        next_agent
                    )

            # =================================================
            # POLICY
            # =================================================

            elif agent == "policy":

                print(
                    "\n[Policy & Compliance]"
                )

                policy_result = (
                    policy_compliance_agent(
                        question,
                        airport
                    )
                )

                execution_trace.append({
                    "iteration": iteration,
                    "agent":
                        "Policy & Compliance",
                    "status": "completed",
                    "action":
                        "policy_rag_search",
                    "result":
                        policy_result,
                })

                next_agent = (
                    self.decide_after_policy(
                        question
                    )
                )

                print(
                    "Next decision:",
                    next_agent
                )

                if (
                    next_agent != "done"
                    and next_agent not in selected_agents
                    and next_agent not in pending_agents
                ):
                    pending_agents.append(
                        next_agent
                    )

            # =================================================
            # RESOLUTION
            # =================================================

            elif agent == "resolution":

                print(
                    "\n[Resolution Agent]"
                )

                resolution_result = (
                    resolution_agent(
                        question,
                        operations_result,
                        policy_result
                    )
                )

                execution_trace.append({
                    "iteration": iteration,
                    "agent":
                        "Resolution Agent",
                    "status": "completed",
                    "action":
                        "generate_recommendation",
                    "result":
                        resolution_result,
                })

                print(
                    "Resolution generated."
                )

        # ----------------------------------------------------
        # Iteration limit
        # ----------------------------------------------------

        if (
            pending_agents
            and iteration >= MAX_ITERATIONS
        ):

            execution_trace.append({
                "iteration": iteration,
                "agent": "Orchestrator",
                "status": "stopped",
                "action": "iteration_limit",
                "result": {
                    "message":
                        "Maximum iteration limit reached."
                },
            })

        # ----------------------------------------------------
        # Final answer
        # ----------------------------------------------------

        if action_result and action_result.get(
            "executed"
        ):

            execution_message = (
                action_result[
                    "execution_result"
                ].get(
                    "message",
                    "Action executed successfully."
                )
            )

            final_answer = execution_message

        elif resolution_result:

            final_answer = resolution_result[
                "answer"
            ]

        elif policy_result:

            final_answer = policy_result[
                "answer"
            ]

        elif operations_result:

            if operations_result.get(
                "success"
            ):

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
                    "Unable to retrieve "
                    "operational metrics: "
                    + operations_result.get(
                        "error",
                        "Unknown error"
                    )
                )

        else:

            final_answer = (
                "I could not determine the "
                "appropriate agent for this request."
            )

        # ----------------------------------------------------
        # Save assistant response
        # ----------------------------------------------------

        self.memory.add_message(
            session_id,
            "assistant",
            final_answer
        )

        # ----------------------------------------------------
        # Return complete workflow
        # ----------------------------------------------------

        return {
            "question": question,
            "airport": airport,
            "selected_agents": selected_agents,
            "iterations": iteration,
            "operations": operations_result,
            "policy": policy_result,
            "resolution": resolution_result,
            "guardrails": guardrail_result,
            "action": action_result,
            "answer": final_answer,
            "execution_trace": execution_trace,
            "memory": self.memory.get_history(
                session_id
            ),
        }


# ============================================================
# DEMO
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

    for trace in result["execution_trace"]:

        print(
            f"Iteration {trace['iteration']} | "
            f"Agent: {trace['agent']} | "
            f"Status: {trace['status']} | "
            f"Action: {trace['action']}"
        )
