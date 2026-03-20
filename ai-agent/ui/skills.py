"""
skills.py — Định nghĩa tất cả skills/tools cho Claude.

Thêm skill mới:
  1. Thêm entry vào TOOLS (schema cho Claude)
  2. Thêm hàm trong data_provider.py (logic lấy data)
  3. Thêm case trong process_tool_call()
"""

from data_provider import get_orders, check_status, get_revenue, get_invoice_stats, query_invoices

# ─────────────────────────────────────────────
# Tool schemas — Claude dùng để biết khi nào gọi tool nào
# ─────────────────────────────────────────────
TOOLS = [
    {
        "name": "get_orders",
        "description": "Lấy danh sách N đơn hàng/hóa đơn gần nhất (VD: '5 đơn hàng gần nhất', '4 đơn mới nhất'). CHỈ dùng khi user hỏi danh sách cụ thể.",
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
    {
        "name": "get_invoice_stats",
        "description": "Lấy thống kê hóa đơn từ SQL Server (tổng doanh thu, số hóa đơn, etc.)",
        "input_schema": {
            "type": "object",
            "properties": {
                "stat_type": {
                    "type": "string",
                    "description": "Loại thống kê: total_revenue | total_paid | invoice_count | avg_invoice | unpaid_count | unreturned_count",
                    "enum": ["total_revenue", "total_paid", "invoice_count", "avg_invoice", "unpaid_count", "unreturned_count"]
                }
            },
            "required": ["stat_type"]
        }
    },
    {
        "name": "query_invoices",
        "description": "Trả lời BẤT CỨ câu hỏi nào em về hóa đơn (thống kê, tổng số, tổng tiền, v.v.). Dùng AI để dịch câu hỏi → SQL. Dùng khi user hỏi: 'tổng số đơn?', 'doanh thu hôm nay?', 'top 5 nhân viên?', v.v. (KHÔNG phải danh sách cụ thể N đơn).",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Câu hỏi tiếng Việt về hóa đơn (VD: 'tính tổng số đơn', 'hôm nay bán bao nhiêu tiền?', 'top 3 cửa hàng')"
                }
            },
            "required": ["question"]
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
    elif tool_name == "get_invoice_stats":
        return get_invoice_stats(tool_input.get("stat_type", "total_revenue"), user_role=user_role)
    elif tool_name == "query_invoices":
        return query_invoices(tool_input.get("question", ""), user_role=user_role)
    else:
        return {"error": f"Unknown skill: {tool_name}"}
