import enum
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ToolPermissionLevel(str, enum.Enum):
    READ_ONLY = "READ_ONLY"
    LOW_RISK_MUTATION = "LOW_RISK_MUTATION"
    CRITICAL_EXTERNAL_ACTION = "CRITICAL_EXTERNAL_ACTION"


class ToolDefinition(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tool_name: str
    description: str
    allowed_roles: List[str]
    permission_level: ToolPermissionLevel
    approval_required: bool = False
    input_schema: Dict[str, Any]
    max_execution_time_sec: float = 5.0
    max_execution_count: int = 10


# --- Verified Local Dataset for Order Checking ---
LOCAL_ORDER_DATABASE: Dict[str, Dict[str, Any]] = {
    "ORD-1001": {
        "order_id": "ORD-1001",
        "customer_id": "CUST-901",
        "status": "SHIPPED",
        "carrier": "FedEx",
        "tracking": "FX-998231",
        "total": 49.99,
        "items": [{"sku": "SKU-A1", "name": "Secure Gateway Dongle", "qty": 1, "price": 49.99}],
        "is_dataset_record": True
    },
    "ORD-1002": {
        "order_id": "ORD-1002",
        "customer_id": "CUST-902",
        "status": "PROCESSING",
        "carrier": "Pending",
        "tracking": None,
        "total": 499.00,
        "items": [{"sku": "SKU-B2", "name": "Enterprise Agent License", "qty": 1, "price": 499.00}],
        "is_dataset_record": True
    },
    "ORD-1003": {
        "order_id": "ORD-1003",
        "customer_id": "CUST-903",
        "status": "DELIVERED",
        "carrier": "UPS",
        "tracking": "1Z992104",
        "total": 120.00,
        "items": [{"sku": "SKU-C3", "name": "Physical Security Key Set", "qty": 2, "price": 60.00}],
        "is_dataset_record": True
    }
}


class ToolRegistry:
    """Centralized Tool Registry for SentinelAI Agent Runtime."""

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
        self._handlers: Dict[str, Callable] = {}
        self._register_default_tools()

    def register_tool(self, definition: ToolDefinition, handler: Callable) -> None:
        self._tools[definition.tool_name] = definition
        self._handlers[definition.tool_name] = handler

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name)

    def get_handler(self, name: str) -> Optional[Callable]:
        return self._handlers.get(name)

    def list_tools(self) -> List[ToolDefinition]:
        return list(self._tools.values())

    def _register_default_tools(self) -> None:
        # Tool 1: search_documents
        self.register_tool(
            ToolDefinition(
                tool_name="search_documents",
                description="Search document repository using semantic and hybrid keyword queries.",
                allowed_roles=["user", "support_agent", "supervisor", "admin"],
                permission_level=ToolPermissionLevel.READ_ONLY,
                approval_required=False,
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "minLength": 1},
                        "top_k": {"type": "integer", "minimum": 1, "maximum": 10, "default": 3}
                    },
                    "required": ["query"]
                },
                max_execution_time_sec=3.0,
                max_execution_count=10
            ),
            handler=self._handle_search_documents
        )

        # Tool 2: retrieve_document
        self.register_tool(
            ToolDefinition(
                tool_name="retrieve_document",
                description="Retrieve complete metadata and chunks for an indexed document ID.",
                allowed_roles=["user", "support_agent", "supervisor", "admin"],
                permission_level=ToolPermissionLevel.READ_ONLY,
                approval_required=False,
                input_schema={
                    "type": "object",
                    "properties": {
                        "document_id": {"type": "string", "minLength": 1}
                    },
                    "required": ["document_id"]
                },
                max_execution_time_sec=3.0,
                max_execution_count=10
            ),
            handler=self._handle_retrieve_document
        )

        # Tool 3: check_order_status
        self.register_tool(
            ToolDefinition(
                tool_name="check_order_status",
                description="Check delivery and fulfillment status for an order ID using local verified records.",
                allowed_roles=["user", "support_agent", "supervisor", "admin"],
                permission_level=ToolPermissionLevel.READ_ONLY,
                approval_required=False,
                input_schema={
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string", "pattern": "^ORD-[0-9]{4}$"}
                    },
                    "required": ["order_id"]
                },
                max_execution_time_sec=2.0,
                max_execution_count=10
            ),
            handler=self._handle_check_order_status
        )

        # Tool 4: create_support_ticket
        self.register_tool(
            ToolDefinition(
                tool_name="create_support_ticket",
                description="Open a support ticket in the customer support escalation queue.",
                allowed_roles=["support_agent", "supervisor", "admin"],
                permission_level=ToolPermissionLevel.LOW_RISK_MUTATION,
                approval_required=False,
                input_schema={
                    "type": "object",
                    "properties": {
                        "customer_id": {"type": "string", "minLength": 3},
                        "issue_summary": {"type": "string", "minLength": 5},
                        "priority": {"type": "string", "enum": ["LOW", "NORMAL", "HIGH", "URGENT"], "default": "NORMAL"}
                    },
                    "required": ["customer_id", "issue_summary"]
                },
                max_execution_time_sec=3.0,
                max_execution_count=5
            ),
            handler=self._handle_create_support_ticket
        )

        # Tool 5: request_refund
        self.register_tool(
            ToolDefinition(
                tool_name="request_refund",
                description="Submit a refund request against a customer purchase. High-risk financial mutation.",
                allowed_roles=["support_agent", "supervisor", "admin"],
                permission_level=ToolPermissionLevel.CRITICAL_EXTERNAL_ACTION,
                approval_required=True,  # Critical financial mutation requires human authorization
                input_schema={
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string", "pattern": "^ORD-[0-9]{4}$"},
                        "amount": {"type": "number", "minimum": 0.01, "maximum": 10000.0},
                        "reason": {"type": "string", "minLength": 5}
                    },
                    "required": ["order_id", "amount", "reason"]
                },
                max_execution_time_sec=5.0,
                max_execution_count=3
            ),
            handler=self._handle_request_refund
        )

    # --- Tool Execution Handlers ---

    async def _handle_search_documents(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "query": args["query"],
            "top_k": args.get("top_k", 3),
            "status": "SEARCH_COMPLETED",
            "matches_found": 1,
            "results": [{"title": "Agent Security Guideline", "score": 0.92}]
        }

    async def _handle_retrieve_document(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "document_id": args["document_id"],
            "status": "RETRIEVED",
            "metadata": {"source": "sentinel_kb"}
        }

    async def _handle_check_order_status(self, args: Dict[str, Any]) -> Dict[str, Any]:
        order_id = args["order_id"].upper()
        order = LOCAL_ORDER_DATABASE.get(order_id)
        if not order:
            return {
                "order_id": order_id,
                "found": False,
                "message": f"Order '{order_id}' was not found in verified database."
            }
        return {
            "order_id": order_id,
            "found": True,
            "details": order
        }

    async def _handle_create_support_ticket(self, args: Dict[str, Any]) -> Dict[str, Any]:
        ticket_id = f"TCK-{hash(args['customer_id'] + args['issue_summary']) % 10000:04d}"
        return {
            "ticket_id": ticket_id,
            "customer_id": args["customer_id"],
            "issue_summary": args["issue_summary"],
            "priority": args.get("priority", "NORMAL"),
            "status": "OPEN",
            "message": "Ticket created in support backlog."
        }

    async def _handle_request_refund(self, args: Dict[str, Any]) -> Dict[str, Any]:
        order_id = args["order_id"].upper()
        amount = float(args["amount"])
        order = LOCAL_ORDER_DATABASE.get(order_id)
        
        if not order:
            return {
                "success": False,
                "order_id": order_id,
                "error": f"Cannot issue refund: Order '{order_id}' not found."
            }
            
        if amount > order["total"]:
            return {
                "success": False,
                "order_id": order_id,
                "error": f"Refund amount (${amount:.2f}) exceeds total order value (${order['total']:.2f})."
            }

        return {
            "success": True,
            "order_id": order_id,
            "refund_amount": amount,
            "reason": args["reason"],
            "status": "REFUNDED",
            "confirmation_code": f"REF-{hash(order_id + str(amount)) % 900000 + 100000}"
        }


tool_registry = ToolRegistry()
