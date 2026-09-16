import pandas as pd
from pathlib import Path


METRICS_PATH = Path("data/airport_metrics.csv")


def load_metrics() -> pd.DataFrame:
    """
    Load airport operational telemetry.
    """

    if not METRICS_PATH.exists():
        raise FileNotFoundError(
            f"Metrics file not found: {METRICS_PATH}"
        )

    df = pd.read_csv(METRICS_PATH)

    df["timestamp"] = pd.to_datetime(
        df["timestamp"]
    )

    return df


def get_airport_metrics(
    airport: str,
    timestamp: str | None = None
) -> dict:
    """
    Retrieve airport operational metrics.

    If timestamp is provided, return metrics
    for that specific timestamp.

    Otherwise, return the latest available
    metrics for the airport.
    """

    df = load_metrics()

    airport = airport.upper()

    airport_data = df[
        df["airport"] == airport
    ]

    if airport_data.empty:
        return {
            "success": False,
            "error": f"No metrics found for airport {airport}"
        }

    if timestamp:

        target_time = pd.to_datetime(timestamp)

        matching_data = airport_data[
            airport_data["timestamp"] == target_time
        ]

        if matching_data.empty:
            return {
                "success": False,
                "error": (
                    f"No metrics found for {airport} "
                    f"at {timestamp}"
                )
            }

        row = matching_data.iloc[0]

    else:

        row = airport_data.sort_values(
            "timestamp"
        ).iloc[-1]

    return {
        "success": True,
        "airport": row["airport"],
        "timestamp": row["timestamp"].strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "completion_rate": float(
            row["completion_rate"]
        ),
        "avg_eta_minutes": float(
            row["avg_eta_minutes"]
        ),
        "active_drivers": int(
            row["active_drivers"]
        ),
        "driver_cancellation_rate": float(
            row["driver_cancellation_rate"]
        ),
        "queue_size": int(
            row["queue_size"]
        ),
        "surge_multiplier": float(
            row["surge_multiplier"]
        ),
        "request_volume": int(
            row["request_volume"]
        )
    }


def calculate_driver_incentive(
    airport: str,
    queue_size: int,
    active_drivers: int
) -> dict:
    """
    Calculate a suggested driver incentive
    based on airport supply pressure.

    This is a synthetic business rule for
    the project.
    """

    airport = airport.upper()

    if queue_size > 200:

        incentive = 500
        level = "HIGH"

    elif queue_size > 150:

        incentive = 300
        level = "MEDIUM"

    elif queue_size > 100:

        incentive = 150
        level = "LOW"

    else:

        incentive = 0
        level = "NONE"

    return {
        "success": True,
        "airport": airport,
        "queue_size": queue_size,
        "active_drivers": active_drivers,
        "incentive_amount": incentive,
        "incentive_level": level,
        "currency": "INR"
    }


def trigger_surge_override(
    airport: str,
    requested_multiplier: float,
    approved_by: str | None = None
) -> dict:
    """
    Request a surge multiplier override.

    High-risk operational actions require
    explicit approval.
    """

    airport = airport.upper()

    max_surge = {
        "SFO": 1.5,
        "LAX": 1.4,
        "JFK": 1.6
    }

    approval_threshold = {
        "SFO": 1.3,
        "LAX": 1.2,
        "JFK": 1.3
    }

    if airport not in max_surge:

        return {
            "success": False,
            "error": f"Unsupported airport: {airport}"
        }

    if requested_multiplier > max_surge[airport]:

        return {
            "success": False,
            "airport": airport,
            "requested_multiplier": requested_multiplier,
            "max_allowed": max_surge[airport],
            "message": (
                "Requested multiplier exceeds "
                "the airport maximum."
            )
        }

    if requested_multiplier > approval_threshold[airport]:

        if not approved_by:

            return {
                "success": False,
                "requires_approval": True,
                "airport": airport,
                "requested_multiplier": requested_multiplier,
                "approval_threshold": approval_threshold[airport],
                "message": (
                    "Human approval is required "
                    "before applying this surge override."
                )
            }

        return {
            "success": True,
            "requires_approval": True,
            "approved": True,
            "airport": airport,
            "requested_multiplier": requested_multiplier,
            "approved_by": approved_by,
            "message": (
                "Surge override approved and ready "
                "for execution."
            )
        }

    return {
        "success": True,
        "requires_approval": False,
        "airport": airport,
        "requested_multiplier": requested_multiplier,
        "message": (
            "Surge multiplier is within the "
            "standard operating range."
        )
    }


if __name__ == "__main__":

    print("\n1. GET AIRPORT METRICS")
    print("=" * 60)

    metrics = get_airport_metrics("SFO")

    print(metrics)


    print("\n2. CALCULATE DRIVER INCENTIVE")
    print("=" * 60)

    incentive = calculate_driver_incentive(
        airport="SFO",
        queue_size=218,
        active_drivers=140
    )

    print(incentive)


    print("\n3. TRIGGER SURGE OVERRIDE")
    print("=" * 60)

    override = trigger_surge_override(
        airport="SFO",
        requested_multiplier=1.4
    )

    print(override)

