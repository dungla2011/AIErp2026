"""
skills.py — Định nghĩa tất cả skills/tools cho Claude.

Thêm skill mới:
  1. Thêm entry vào TOOLS (schema cho Claude)
  2. Thêm hàm trong data_provider.py (logic lấy data)
  3. Thêm case trong process_tool_call()
"""

from data_provider import get_orders, check_status, get_revenue

# ─────────────────────────────────────────────
# Tool schemas — Claude dùng để biết khi nào gọi tool nào
# ─────────────────────────────────────────────
TOOLS = [
    {
        "name": "get_orders",
        "description": "Lấy danh sách đơn hàng gần đây",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Số lượng đơn hàng muốn lấy (default 5)"
                }
            },
            "required": []
        }
    },
    {
        "name": "check_status",
        "description": "Kiểm tra trạng thái một đơn hàng theo mã đơn",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "Mã đơn hàng (VD: ORD001)"
                }
            },
            "required": ["order_id"]
        }
    },
    {
        "name": "get_revenue",
        "description": "Lấy doanh thu theo kỳ",
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "description": "Kỳ thống kê: today | week | month"
                }
            },
            "required": ["period"]
        }
    },
]


# ─────────────────────────────────────────────
# Router — thực thi tool call từ Claude
# ─────────────────────────────────────────────
def process_tool_call(tool_name: str, tool_input: dict, user_role: str = "customer"):
    """Dispatch tool call đến đúng hàm trong data_provider."""
    if tool_name == "get_orders":
        return get_orders(tool_input.get("limit", 5), user_role=user_role)
    elif tool_name == "check_status":
        return check_status(tool_input.get("order_id"), user_role=user_role)
    elif tool_name == "get_revenue":
        return get_revenue(tool_input.get("period", "today"), user_role=user_role)
    else:
        return {"error": f"Unknown skill: {tool_name}"}
