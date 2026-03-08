# ============================================================
# Calendar Plugin — Example plugin for calendar integration
# ============================================================
from . import Plugin


class CalendarPlugin(Plugin):
    name = "calendar"
    description = "Manage calendar events and scheduling"
    version = "1.0.0"

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "list", "delete"],
                    "description": "Calendar action to perform",
                },
                "title": {"type": "string", "description": "Event title"},
                "date": {"type": "string", "description": "Event date (ISO format)"},
                "duration": {"type": "integer", "description": "Duration in minutes"},
            },
            "required": ["action"],
        }

    async def execute(self, **kwargs) -> dict:
        action = kwargs.get("action", "list")
        if action == "create":
            return {
                "status": "created",
                "event": {
                    "title": kwargs.get("title", "Untitled"),
                    "date": kwargs.get("date", ""),
                    "duration": kwargs.get("duration", 30),
                },
            }
        elif action == "list":
            return {"status": "ok", "events": []}
        elif action == "delete":
            return {"status": "deleted"}
        return {"status": "unknown_action"}
