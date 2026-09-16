from src.guardrails import (
    validate_input,
    classify_risk,
    validate_surge_request,
    validate_action,
    request_human_approval,
    process_approval,
    run_guardrails,
)


# ============================================================
# INPUT VALIDATION TESTS
# ============================================================

def test_valid_input():
    result = validate_input(
        "What is the current queue at SFO?",
        "SFO"
    )

    assert result["valid"] is True
    assert result["airport"] == "SFO"


def test_empty_question():
    result = validate_input("", "SFO")

    assert result["valid"] is False
    assert "cannot be empty" in result["error"]


def test_invalid_airport():
    result = validate_input(
        "What is the queue?",
        "ORD"
    )

    assert result["valid"] is False
    assert "Unsupported airport" in result["error"]


# ============================================================
# RISK CLASSIFICATION TESTS
# ============================================================

def test_low_risk_question():
    result = classify_risk(
        "What is the current queue at SFO?"
    )

    assert result["risk_level"] == "LOW"
    assert result["requires_human_approval"] is False


def test_medium_risk_question():
    result = classify_risk(
        "Calculate driver incentive for SFO"
    )

    assert result["risk_level"] == "MEDIUM"
    assert result["requires_human_approval"] is False


def test_high_risk_surge_question():
    result = classify_risk(
        "Increase SFO surge to 1.4x"
    )

    assert result["risk_level"] == "HIGH"
    assert result["requires_human_approval"] is True


def test_high_risk_lax_surge_question():
    result = classify_risk(
        "Can we increase LAX surge to 1.3x?"
    )

    assert result["risk_level"] == "HIGH"
    assert result["requires_human_approval"] is True


# ============================================================
# SURGE VALIDATION TESTS
# ============================================================

def test_valid_surge_without_approval():
    result = validate_surge_request(
        "SFO",
        1.2
    )

    assert result["valid"] is True
    assert result["requires_human_approval"] is False


def test_surge_requires_approval():
    result = validate_surge_request(
        "SFO",
        1.4
    )

    assert result["valid"] is True
    assert result["requires_human_approval"] is True


def test_surge_exceeds_maximum():
    result = validate_surge_request(
        "SFO",
        1.6
    )

    assert result["valid"] is False
    assert result["requires_human_approval"] is False


def test_invalid_surge_multiplier():
    result = validate_surge_request(
        "SFO",
        0
    )

    assert result["valid"] is False


# ============================================================
# ACTION VALIDATION TESTS
# ============================================================

def test_metrics_action():
    result = validate_action(
        action="get_airport_metrics",
        airport="SFO"
    )

    assert result["valid"] is True
    assert result["requires_human_approval"] is False


def test_incentive_action():
    result = validate_action(
        action="calculate_driver_incentive",
        airport="SFO"
    )

    assert result["valid"] is True
    assert result["requires_human_approval"] is False


def test_surge_action_requires_approval():
    result = validate_action(
        action="trigger_surge_override",
        airport="SFO",
        requested_multiplier=1.4
    )

    assert result["valid"] is True
    assert result["requires_human_approval"] is True


def test_unknown_action():
    result = validate_action(
        action="delete_airport",
        airport="SFO"
    )

    assert result["valid"] is False


# ============================================================
# HUMAN APPROVAL TESTS
# ============================================================

def test_create_human_approval_request():

    result = request_human_approval(
        action="trigger_surge_override",
        airport="SFO",
        details={
            "requested_multiplier": 1.4
        }
    )

    assert result["approval_required"] is True
    assert result["status"] == "PENDING"
    assert result["action"] == "trigger_surge_override"


def test_approve_action():

    approval = request_human_approval(
        action="trigger_surge_override",
        airport="SFO",
        details={
            "requested_multiplier": 1.4
        }
    )

    result = process_approval(
        approval,
        approved=True,
        approved_by="Airport Operations Manager"
    )

    assert result["success"] is True
    assert result["status"] == "APPROVED"
    assert result["approved"] is True


def test_reject_action():

    approval = request_human_approval(
        action="trigger_surge_override",
        airport="SFO",
        details={
            "requested_multiplier": 1.4
        }
    )

    result = process_approval(
        approval,
        approved=False
    )

    assert result["success"] is True
    assert result["status"] == "REJECTED"
    assert result["approved"] is False


def test_approval_requires_identity():

    approval = request_human_approval(
        action="trigger_surge_override",
        airport="SFO",
        details={
            "requested_multiplier": 1.4
        }
    )

    result = process_approval(
        approval,
        approved=True
    )

    assert result["success"] is False
    assert "Approver identity" in result["error"]


# ============================================================
# COMPLETE GUARDRAIL TESTS
# ============================================================

def test_run_guardrails_low_risk():

    result = run_guardrails(
        "What is the current queue at SFO?",
        "SFO"
    )

    assert result["allowed"] is True
    assert result["risk_level"] == "LOW"
    assert result["requires_human_approval"] is False


def test_run_guardrails_high_risk():

    result = run_guardrails(
        "Increase SFO surge to 1.4x",
        "SFO"
    )

    assert result["allowed"] is True
    assert result["risk_level"] == "HIGH"
    assert result["requires_human_approval"] is True


def test_run_guardrails_invalid_airport():

    result = run_guardrails(
        "What is the current queue?",
        "ORD"
    )

    assert result["allowed"] is False
    assert result["stage"] == "input_validation"