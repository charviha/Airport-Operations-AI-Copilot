import re
from datetime import datetime


# ============================================================
# SUPPORTED AIRPORTS
# ============================================================

SUPPORTED_AIRPORTS = {
    "SFO",
    "LAX",
    "JFK",
}


# ============================================================
# RISK LEVELS
# ============================================================

LOW_RISK = "LOW"
MEDIUM_RISK = "MEDIUM"
HIGH_RISK = "HIGH"


# ============================================================
# INPUT VALIDATION
# ============================================================

def validate_input(
    question: str,
    airport: str | None = None
) -> dict:

    """
    Validates user input before sending it
    to the agent workflow.
    """

    if not question or not question.strip():
        return {
            "valid": False,
            "error": "Question cannot be empty."
        }

    question = question.strip()

    if len(question) > 1000:
        return {
            "valid": False,
            "error": "Question is too long. Maximum length is 1000 characters."
        }

    if airport:
        airport = airport.upper().strip()

        if airport not in SUPPORTED_AIRPORTS:
            return {
                "valid": False,
                "error": (
                    f"Unsupported airport: {airport}. "
                    f"Supported airports are SFO, LAX and JFK."
                )
            }

    return {
        "valid": True,
        "question": question,
        "airport": airport
    }


# ============================================================
# RISK CLASSIFICATION
# ============================================================

def classify_risk(
    question: str
) -> dict:

    """
    Classifies an operational request according
    to the potential risk of the requested action.
    """

    question_lower = question.lower()

    # --------------------------------------------------------
    # HIGH-RISK KEYWORDS
    # --------------------------------------------------------

    high_risk_keywords = [
        "trigger surge",
        "increase surge",
        "decrease surge",
        "apply surge",
        "override surge",
        "surge override",
        "set surge",
        "change surge",
        "execute",
        "activate",
        "deactivate",
        "disable",
        "enable",
        "block drivers",
        "remove drivers",
    ]

    # --------------------------------------------------------
    # SURGE ACTION DETECTION
    # --------------------------------------------------------
    # Handles cases such as:
    #
    # Increase SFO surge to 1.4x
    # Increase LAX surge to 1.3x
    # Set JFK surge to 1.5x
    # Change SFO surge multiplier
    #
    # The airport name can appear between the action
    # and the word "surge".

    surge_action_pattern = re.compile(
        r"\b("
        r"increase|decrease|apply|set|change|override|trigger"
        r")\b"
        r".{0,40}"
        r"\bsurge\b",
        re.IGNORECASE
    )

    # --------------------------------------------------------
    # MEDIUM-RISK KEYWORDS
    # --------------------------------------------------------

    medium_risk_keywords = [
        "calculate incentive",
        "driver incentive",
        "incentive",
        "change",
        "modify",
        "adjust",
    ]

    # --------------------------------------------------------
    # HIGH RISK CHECK
    # --------------------------------------------------------
    # IMPORTANT:
    # HIGH risk must be checked BEFORE medium risk.
    # Otherwise "increase" / "change" can incorrectly
    # classify a surge action as MEDIUM.

    if (
        any(
            keyword in question_lower
            for keyword in high_risk_keywords
        )
        or surge_action_pattern.search(question)
    ):
        return {
            "risk_level": HIGH_RISK,
            "requires_human_approval": True,
            "reason": (
                "The request could modify an operational setting "
                "or trigger an operational action."
            )
        }

    # --------------------------------------------------------
    # MEDIUM RISK CHECK
    # --------------------------------------------------------

    if any(
        keyword in question_lower
        for keyword in medium_risk_keywords
    ):
        return {
            "risk_level": MEDIUM_RISK,
            "requires_human_approval": False,
            "reason": (
                "The request involves an operational calculation "
                "or potential adjustment."
            )
        }

    # --------------------------------------------------------
    # LOW RISK
    # --------------------------------------------------------

    return {
        "risk_level": LOW_RISK,
        "requires_human_approval": False,
        "reason": (
            "The request is informational and does not "
            "directly modify an operational system."
        )
    }


# ============================================================
# SURGE POLICY VALIDATION
# ============================================================

def validate_surge_request(
    airport: str,
    requested_multiplier: float
) -> dict:

    """
    Validates a requested surge multiplier against
    airport-specific policy limits.
    """

    airport = airport.upper().strip()

    max_surge = {
        "SFO": 1.5,
        "LAX": 1.4,
        "JFK": 1.6,
    }

    approval_threshold = {
        "SFO": 1.3,
        "LAX": 1.2,
        "JFK": 1.3,
    }

    if airport not in max_surge:
        return {
            "valid": False,
            "error": f"Unsupported airport: {airport}"
        }

    if requested_multiplier <= 0:
        return {
            "valid": False,
            "error": "Surge multiplier must be greater than 0."
        }

    maximum = max_surge[airport]
    threshold = approval_threshold[airport]

    if requested_multiplier > maximum:
        return {
            "valid": False,
            "requires_human_approval": False,
            "airport": airport,
            "requested_multiplier": requested_multiplier,
            "max_allowed": maximum,
            "message": (
                f"Requested surge {requested_multiplier}x "
                f"exceeds the {airport} maximum of {maximum}x."
            )
        }

    if requested_multiplier > threshold:
        return {
            "valid": True,
            "requires_human_approval": True,
            "airport": airport,
            "requested_multiplier": requested_multiplier,
            "approval_threshold": threshold,
            "max_allowed": maximum,
            "message": (
                f"Requested surge {requested_multiplier}x is within "
                f"the maximum of {maximum}x but exceeds the approval "
                f"threshold of {threshold}x."
            )
        }

    return {
        "valid": True,
        "requires_human_approval": False,
        "airport": airport,
        "requested_multiplier": requested_multiplier,
        "approval_threshold": threshold,
        "max_allowed": maximum,
        "message": (
            f"Requested surge {requested_multiplier}x is within "
            f"the standard operating range."
        )
    }


# ============================================================
# ACTION VALIDATION
# ============================================================

def validate_action(
    action: str,
    airport: str | None = None,
    requested_multiplier: float | None = None
) -> dict:

    """
    Validates an operational action before execution.
    """

    action = action.lower().strip()

    if airport:
        airport = airport.upper().strip()

        if airport not in SUPPORTED_AIRPORTS:
            return {
                "valid": False,
                "error": f"Unsupported airport: {airport}"
            }

    if action == "trigger_surge_override":

        if not airport:
            return {
                "valid": False,
                "error": (
                    "Airport is required for a surge override."
                )
            }

        if requested_multiplier is None:
            return {
                "valid": False,
                "error": (
                    "Requested surge multiplier is required."
                )
            }

        return validate_surge_request(
            airport,
            requested_multiplier
        )

    if action == "get_airport_metrics":

        if not airport:
            return {
                "valid": False,
                "error": (
                    "Airport is required to retrieve metrics."
                )
            }

        return {
            "valid": True,
            "requires_human_approval": False,
            "message": (
                "Metric retrieval is a read-only operation."
            )
        }

    if action == "calculate_driver_incentive":

        if not airport:
            return {
                "valid": False,
                "error": (
                    "Airport is required to calculate "
                    "driver incentives."
                )
            }

        return {
            "valid": True,
            "requires_human_approval": False,
            "message": (
                "Incentive calculation is a non-executing "
                "operational calculation."
            )
        }

    return {
        "valid": False,
        "error": f"Unknown action: {action}"
    }


# ============================================================
# HUMAN APPROVAL
# ============================================================

def request_human_approval(
    action: str,
    airport: str,
    details: dict
) -> dict:

    """
    Creates a human approval request.

    This function does NOT execute the action.
    """

    return {
        "approval_required": True,
        "status": "PENDING",
        "action": action,
        "airport": airport.upper(),
        "details": details,
        "message": (
            "Human approval is required before this "
            "operational action can be executed."
        )
    }


# ============================================================
# APPROVAL DECISION
# ============================================================

def process_approval(
    approval_request: dict,
    approved: bool,
    approved_by: str | None = None
) -> dict:

    """
    Processes a human approval decision.
    """

    if not approval_request.get("approval_required"):
        return {
            "success": False,
            "error": "This request does not require approval."
        }

    if not approved:
        return {
            "success": True,
            "status": "REJECTED",
            "approved": False,
            "message": (
                "Human approval was rejected. "
                "No operational action was executed."
            )
        }

    if not approved_by:
        return {
            "success": False,
            "error": (
                "Approver identity is required "
                "when approving an action."
            )
        }

    return {
        "success": True,
        "status": "APPROVED",
        "approved": True,
        "approved_by": approved_by,
        "action": approval_request["action"],
        "airport": approval_request["airport"],
        "details": approval_request["details"],
        "message": (
            "Human approval received. "
            "The action is now eligible for execution."
        )
    }


# ============================================================
# AUDIT TRAIL
# ============================================================

def create_audit_record(
    question: str,
    airport: str | None,
    risk_level: str,
    action: str | None,
    result: dict
) -> dict:

    """
    Creates a structured audit record for an agent action.
    """

    return {
        "timestamp": datetime.now().isoformat(),
        "question": question,
        "airport": airport,
        "risk_level": risk_level,
        "action": action,
        "result": result,
    }


# ============================================================
# COMPLETE GUARDRAIL CHECK
# ============================================================

def run_guardrails(
    question: str,
    airport: str | None = None
) -> dict:

    """
    Runs input validation and risk classification
    before the agent workflow starts.
    """

    validation = validate_input(
        question,
        airport
    )

    if not validation["valid"]:
        return {
            "allowed": False,
            "stage": "input_validation",
            "error": validation["error"]
        }

    risk = classify_risk(
        validation["question"]
    )

    return {
        "allowed": True,
        "stage": "guardrail_check",
        "question": validation["question"],
        "airport": validation["airport"],
        "risk_level": risk["risk_level"],
        "requires_human_approval": risk[
            "requires_human_approval"
        ],
        "reason": risk["reason"],
    }


# ============================================================
# TESTS / DEMO
# ============================================================

if __name__ == "__main__":

    print("\n1. INPUT VALIDATION")
    print("=" * 60)

    print(
        validate_input(
            "What is the queue at SFO?",
            "SFO"
        )
    )

    print("\n2. RISK CLASSIFICATION")
    print("=" * 60)

    print(
        classify_risk(
            "What is the current queue at SFO?"
        )
    )

    print(
        classify_risk(
            "Increase SFO surge to 1.4x"
        )
    )

    print(
        classify_risk(
            "Can we increase LAX surge to 1.3x?"
        )
    )

    print(
        classify_risk(
            "Calculate driver incentive for SFO"
        )
    )

    print("\n3. SURGE VALIDATION")
    print("=" * 60)

    print(
        validate_surge_request(
            "SFO",
            1.2
        )
    )

    print(
        validate_surge_request(
            "SFO",
            1.4
        )
    )

    print(
        validate_surge_request(
            "SFO",
            1.6
        )
    )

    print("\n4. HUMAN APPROVAL")
    print("=" * 60)

    approval = request_human_approval(
        action="trigger_surge_override",
        airport="SFO",
        details={
            "requested_multiplier": 1.4
        }
    )

    print(approval)

    print("\n5. APPROVE ACTION")
    print("=" * 60)

    print(
        process_approval(
            approval,
            approved=True,
            approved_by="Airport Operations Manager"
        )
    )

    print("\n6. COMPLETE GUARDRAIL CHECK")
    print("=" * 60)

    print(
        run_guardrails(
            "Increase SFO surge to 1.4x",
            "SFO"
        )
    )