import streamlit as st

from src.agents import AirportOrchestrator
from src.tools import get_airport_metrics

# =====================================================
# PAGE CONFIGURATION
# =====================================================

st.set_page_config(
    page_title="Airport Operations AI Copilot",
    page_icon="✈️",
    layout="wide",
)


# =====================================================
# HEADER
# =====================================================

st.title("✈️ Airport Operations AI Copilot")

st.caption(
    "RAG + Multi-Agent System + Guardrails + Human-in-the-Loop"
)


# =====================================================
# INITIALIZE ORCHESTRATOR
# =====================================================

@st.cache_resource
def get_orchestrator():
    return AirportOrchestrator()


orchestrator = get_orchestrator()


# =====================================================
# SIDEBAR
# =====================================================

st.sidebar.header("Airport Configuration")

airport = st.sidebar.selectbox(
    "Select Airport",
    ["SFO", "LAX", "JFK"],
)

st.sidebar.markdown("---")

st.sidebar.markdown(
    """
### Supported Airports

- **SFO** — San Francisco International Airport
- **LAX** — Los Angeles International Airport
- **JFK** — John F. Kennedy International Airport
"""
)


# =====================================================
# SESSION STATE
# =====================================================

if "result" not in st.session_state:
    st.session_state.result = None

if "question" not in st.session_state:
    st.session_state.question = ""

if "approval_pending" not in st.session_state:
    st.session_state.approval_pending = False


# =====================================================
# AIRPORT METRICS
# =====================================================

st.header(f"{airport} Operational Metrics")

try:
    metrics = get_airport_metrics(airport)

except Exception:
    metrics = None


if metrics and metrics.get("success"):

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Queue Size",
            metrics.get("queue_size", "N/A"),
        )

    with col2:
        st.metric(
            "Active Drivers",
            metrics.get("active_drivers", "N/A"),
        )

    with col3:
        completion_rate = metrics.get(
            "completion_rate",
            None,
        )

        if completion_rate is not None:
            completion_rate = (
                f"{float(completion_rate) * 100:.0f}%"
            )

        st.metric(
            "Completion Rate",
            completion_rate or "N/A",
        )

    with col4:
        eta = metrics.get(
            "avg_eta_minutes",
            None,
        )

        if eta is not None:
            eta = f"{float(eta):.1f} min"

        st.metric(
            "Average ETA",
            eta or "N/A",
        )

    col5, col6, col7, col8 = st.columns(4)

    with col5:
        request_volume = metrics.get(
            "request_volume",
            "N/A",
        )

        st.metric(
            "Request Volume",
            request_volume,
        )

    with col6:
        cancellation_rate = metrics.get(
            "driver_cancellation_rate",
            None,
        )

        if cancellation_rate is not None:
            cancellation_rate = (
                f"{float(cancellation_rate) * 100:.0f}%"
            )

        st.metric(
            "Driver Cancellation",
            cancellation_rate or "N/A",
        )

    with col7:
        surge = metrics.get(
            "surge_multiplier",
            None,
        )

        if surge is not None:
            surge = f"{float(surge):.1f}x"

        st.metric(
            "Surge Multiplier",
            surge or "N/A",
        )

    with col8:
        timestamp = metrics.get(
            "timestamp",
            "N/A",
        )

        st.metric(
            "Latest Timestamp",
            timestamp,
        )

else:

    st.warning(
        f"No operational metrics available for {airport}."
    )


st.markdown("---")


# =====================================================
# ASK THE COPILOT
# =====================================================

st.header("Ask the Airport Operations Copilot")

question = st.text_area(
    "Enter your operational question",
    value=st.session_state.question,
    placeholder=(
        "Example: SFO queue is high. What should we do?"
    ),
    height=100,
)


analyze_button = st.button(
    "Analyze",
    type="primary",
    use_container_width=True,
)


# =====================================================
# PROCESS QUESTION
# =====================================================

if analyze_button:

    if not question.strip():

        st.warning(
            "Please enter an operational question."
        )

    else:

        with st.spinner(
            "Copilot is analyzing the operational request..."
        ):

            try:

                result = orchestrator.run(
                    question=question.strip(),
                    airport=airport,
                )

                st.session_state.result = result
                st.session_state.question = question.strip()

                # Check whether approval is required.
                guardrail_result = (
                    result.get("guardrails") or {}
                )

                st.session_state.approval_pending = (
                    guardrail_result.get(
                        "requires_human_approval",
                        False,
                    )
                    and not (
                        result.get("action") or {}
                    ).get(
                        "approved",
                        False,
                    )
                )

            except Exception as e:

                st.error(
                    f"An error occurred while processing the request: {e}"
                )

                st.stop()


# =====================================================
# DISPLAY RESULT
# =====================================================

result = st.session_state.result


if result:

    # =================================================
    # COPILOT RESPONSE
    # =================================================

    st.header("Copilot Response")

    answer = result.get("answer")

    if answer:

        st.markdown(answer)

    else:

        st.info(
            "The copilot did not generate a final response."
        )


    # =================================================
    # EXECUTION SUMMARY
    # =================================================

    st.header("Execution Summary")

    guardrails = result.get(
        "guardrails"
    ) or {}

    risk_level = guardrails.get(
        "risk_level",
        "UNKNOWN",
    )

    requires_approval = guardrails.get(
        "requires_human_approval",
        False,
    )

    iterations = result.get(
        "iterations",
        0,
    )

    summary_col1, summary_col2, summary_col3 = st.columns(3)

    with summary_col1:

        st.metric(
            "Risk Level",
            risk_level,
        )

    with summary_col2:

        st.metric(
            "Human Approval",
            "Required"
            if requires_approval
            else "Not Required",
        )

    with summary_col3:

        st.metric(
            "Iterations",
            iterations,
        )


    # =================================================
    # AGENT ACTIVITY
    # =================================================

    st.header("Agent Activity")

    execution_trace = result.get(
        "execution_trace"
    ) or []

    if execution_trace:

        step_number = 1

        for trace_item in execution_trace:

            if isinstance(trace_item, dict):

                agent_name = (
                    trace_item.get("agent")
                    or trace_item.get("name")
                    or trace_item.get("step")
                    or "Unknown Agent"
                )

            else:

                agent_name = str(trace_item)

            st.markdown(
                f"**Step {step_number}:** {agent_name}"
            )

            step_number += 1

    else:

        selected_agents = result.get(
            "selected_agents"
        ) or []

        if selected_agents:

            for index, agent_name in enumerate(
                selected_agents,
                start=1,
            ):

                st.markdown(
                    f"**Step {index}:** {agent_name}"
                )

        else:

            st.info(
                "No agent activity was recorded."
            )


    # =================================================
    # RAG TRACE
    # =================================================

    st.header("RAG Trace")

    policy_result = result.get(
        "policy"
    ) or {}

    sources = policy_result.get(
        "sources"
    ) or []

    policy_answer = policy_result.get(
        "answer"
    ) or ""


    if sources:

        st.markdown(
            "**Retrieved Policy Sources**"
        )

        for index, source in enumerate(
            sources,
            start=1,
        ):

            if isinstance(source, dict):

                document = source.get(
                    "document",
                    "Unknown document",
                )

                airport_name = source.get(
                    "airport",
                    "",
                )

                section = source.get(
                    "section",
                    "",
                )

                score = source.get(
                    "score",
                    None,
                )

                if score is not None:

                    try:

                        score_text = (
                            f"{float(score):.4f}"
                        )

                    except (
                        TypeError,
                        ValueError,
                    ):

                        score_text = str(score)

                else:

                    score_text = "N/A"


                st.markdown(
                    f"""
**{index}. {document}**

- Airport: `{airport_name}`
- Section: `{section}`
- Similarity Score: `{score_text}`
"""
                )

            else:

                st.markdown(
                    f"**{index}.** {str(source)}"
                )

    else:

        st.info(
            "No policy sources were retrieved."
        )


    if policy_answer:

        with st.expander(
            "View Policy RAG Answer"
        ):

            st.markdown(
                policy_answer
            )


    # =================================================
    # GUARDRAIL STATUS
    # =================================================

    st.header("Guardrail Status")

    if guardrails:

        allowed = guardrails.get(
            "allowed",
            True,
        )

        if allowed:

            st.success(
                "Request passed guardrails."
            )

        else:

            st.error(
                "Request was blocked by guardrails."
            )

        st.json(
            guardrails
        )

    else:

        st.info(
            "No guardrail information available."
        )


    # =================================================
    # HUMAN APPROVAL
    # =================================================

    action_result = result.get(
        "action"
    ) or {}

    if requires_approval:

        st.header("Human Approval")

        approved = action_result.get(
            "approved",
            False,
        )

        approval_processed = action_result.get(
            "approval_processed",
            False,
        )

        if approved:

            st.success(
                "Approval has been granted."
            )

        elif approval_processed:

            st.warning(
                "The requested action was rejected."
            )

        else:

            st.warning(
                "This action requires human approval before execution."
            )


        approval_col1, approval_col2 = st.columns(2)


        with approval_col1:

            approve_button = st.button(
                "Approve",
                key="approve_action",
                use_container_width=True,
            )


        with approval_col2:

            reject_button = st.button(
                "Reject",
                key="reject_action",
                use_container_width=True,
            )


        # ---------------------------------------------
        # APPROVE
        # ---------------------------------------------

        if approve_button:

            with st.spinner(
                "Processing approval..."
            ):

                try:

                    approval_result = orchestrator.run(
                        question=st.session_state.question,
                        airport=airport,
                        approved_by="Airport Operations Manager",
                        approval_decision=True,
                    )

                    st.session_state.result = (
                        approval_result
                    )

                    st.rerun()

                except Exception as e:

                    st.error(
                        f"Approval processing failed: {e}"
                    )


        # ---------------------------------------------
        # REJECT
        # ---------------------------------------------

        if reject_button:

            with st.spinner(
                "Processing rejection..."
            ):

                try:

                    rejection_result = orchestrator.run(
                        question=st.session_state.question,
                        airport=airport,
                        approved_by="Airport Operations Manager",
                        approval_decision=False,
                    )

                    st.session_state.result = (
                        rejection_result
                    )

                    st.rerun()

                except Exception as e:

                    st.error(
                        f"Rejection processing failed: {e}"
                    )


    # =================================================
    # EXECUTION RESULT
    # =================================================

    if action_result:

        st.header("Execution Result")

        execution_success = action_result.get(
            "success",
            None,
        )

        if execution_success is True:

            st.success(
                "Action execution completed successfully."
            )

        elif execution_success is False:

            st.error(
                "Action execution was not completed."
            )

        st.json(
            action_result
        )


    # =================================================
    # AUDIT RECORD
    # =================================================

    audit_record = result.get(
        "audit_record"
    )

    if audit_record:

        st.header("Audit Record")

        st.json(
            audit_record
        )


    # =================================================
    # MEMORY
    # =================================================

    memory = result.get(
        "memory"
    )

    if memory:

        with st.expander(
            "Conversation Memory"
        ):

            st.json(
                memory
            )


# =====================================================
# FOOTER
# =====================================================

st.markdown("---")

st.caption(
    "Airport Operations AI Copilot | "
    "RAG + Multi-Agent System + Guardrails + Human-in-the-Loop"
)
