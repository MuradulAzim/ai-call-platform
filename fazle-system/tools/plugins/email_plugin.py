# ============================================================
# Email Plugin — Example plugin for email automation
# ============================================================
from . import Plugin


class EmailPlugin(Plugin):
    name = "email"
    description = "Send and manage emails"
    version = "1.0.0"

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["send", "draft", "list"],
                    "description": "Email action",
                },
                "to": {"type": "string", "description": "Recipient email"},
                "subject": {"type": "string", "description": "Email subject"},
                "body": {"type": "string", "description": "Email body"},
            },
            "required": ["action"],
        }

    async def execute(self, **kwargs) -> dict:
        action = kwargs.get("action", "list")
        if action == "send":
            return {
                "status": "sent",
                "to": kwargs.get("to", ""),
                "subject": kwargs.get("subject", ""),
            }
        elif action == "draft":
            return {
                "status": "drafted",
                "to": kwargs.get("to", ""),
                "subject": kwargs.get("subject", ""),
            }
        return {"status": "ok", "emails": []}
