from collections import defaultdict


class ConversationMemory:
    """
    Simple conversational memory for the Airport AI Copilot.

    Stores previous user questions and assistant responses
    separately for each conversation/session.
    """

    def __init__(self):
        self.sessions = defaultdict(list)

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str
    ):
        self.sessions[session_id].append({
            "role": role,
            "content": content
        })

    def get_history(
        self,
        session_id: str
    ) -> list[dict]:
        return self.sessions[session_id]

    def get_recent_history(
        self,
        session_id: str,
        limit: int = 10
    ) -> list[dict]:
        return self.sessions[session_id][-limit:]

    def clear(self, session_id: str):
        self.sessions[session_id] = []

    def format_history(
        self,
        session_id: str,
        limit: int = 10
    ) -> str:

        history = self.get_recent_history(
            session_id,
            limit
        )

        if not history:
            return "No previous conversation."

        formatted = []

        for message in history:
            role = message["role"].upper()
            content = message["content"]

            formatted.append(
                f"{role}: {content}"
            )

        return "\n".join(formatted)


if __name__ == "__main__":

    memory = ConversationMemory()

    session_id = "demo"

    memory.add_message(
        session_id,
        "user",
        "What is the current queue at SFO?"
    )

    memory.add_message(
        session_id,
        "assistant",
        "The latest SFO queue size is 125."
    )

    memory.add_message(
        session_id,
        "user",
        "Is that within the normal range?"
    )

    print("\nCONVERSATION HISTORY")
    print("=" * 60)

    print(
        memory.format_history(session_id)
    )