"""
data_provider.py — Data access layer for bot tools.

Đây là nơi duy nhất bot lấy data. Hiện tại đọc từ SQLite (mock).
Để kết nối API thật: chỉ sửa các hàm trong file này, không cần đụng bot.py.

Swap guide:
  Thay dòng:  return OrdersDB.get_orders(limit)
  Bằng:       return real_api.fetch_orders(limit)

Role-based access control:
  - customer: get_orders, check_status only
  - staff, admin: all tools
"""

from database import OrdersDB
from typing import Any
import requests
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path, override=True)

API_BASE = os.getenv("API_BASE", "http://localhost:8100")
AUTH_PASSWORD_MD5 = os.getenv("AUTH_PASSWORD_MD5", "081904e6952d21450814cd3c465cf059")


def _check_permission(user_role: str, required_role: str) -> bool:
    """
    Check if user has permission to access a resource.
    
    required_role: "public", "internal", "admin"
    Returns: True if allowed, False otherwise
    """
    access_levels = {
        "customer": 0,   # public only
        "staff": 1,      # internal
        "admin": 2       # admin
    }
    
    required_levels = {
        "public": 0,
        "internal": 1,
        "admin": 2
    }
    
    user_level = access_levels.get(user_role, 0)
    required_level = required_levels.get(required_role, 0)
    
    return user_level >= required_level


# ─────────────────────────────────────────────
# Tool: get_orders
# ─────────────────────────────────────────────
def get_orders(limit: int = 5, user_role: str = "customer") -> Any:
    """
    Lấy danh sách đơn hàng gần đây.
    
    Permissions:
      - customer: allowed
      - staff, admin: allowed

    Gọi API endpoint /orders và format kết quả cho Claude
    """
    try:
        headers = {"Authorization": f"Bearer {AUTH_PASSWORD_MD5}"}
        response = requests.get(f"{API_BASE}/orders?limit={limit}", headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            orders = data.get("orders", [])
            
            if not orders:
                return {"message": "Không có đơn hàng nào."}
            
            # Format orders for Claude
            formatted_orders = []
            for order in orders:
                formatted_orders.append({
                    "id": order.get("id"),
                    "customer": order.get("customer"),
                    "amount": order.get("amount"),
                    "status": order.get("status"),
                    "created_at": order.get("created_at"),
                    "expected_delivery": order.get("expected_delivery"),
                    "delivered_at": order.get("delivered_at")
                })
            
            return {
                "total": data.get("total", 0),
                "orders": formatted_orders
            }
        else:
            return {"error": f"API error: {response.status_code}", "details": response.text}
    except Exception as e:
        return {"error": f"Failed to fetch orders: {str(e)}"}


# ─────────────────────────────────────────────
# Tool: check_status
# ─────────────────────────────────────────────
def check_status(order_id: str, user_role: str = "customer") -> Any:
    """
    Kiểm tra trạng thái một đơn hàng theo ID.

    Permissions:
      - customer: allowed
      - staff, admin: allowed

    [MOCK → DB]  Đọc từ bảng orders trong SQLite.
    [REAL API]   Thay bằng: requests.get(f"{API_BASE}/orders/{order_id}").json()
    """
    order = OrdersDB.get_order(order_id)
    if not order:
        return {"error": f"Không tìm thấy đơn hàng: {order_id}"}
    return order


# ─────────────────────────────────────────────
# Tool: get_revenue
# ─────────────────────────────────────────────
def get_revenue(period: str = "today", user_role: str = "customer") -> Any:
    """
    Lấy doanh thu theo kỳ: today | week | month.

    Permissions:
      - customer: DENIED (sensitive business data)
      - staff, admin: allowed

    [MOCK → DB]  Tính SUM(amount) từ bảng orders trong SQLite.
    [REAL API]   Thay bằng: requests.get(f"{API_BASE}/revenue?period={period}").json()
    """
    if not _check_permission(user_role, "internal"):
        return {
            "error": f"Bạn không có quyền truy cập thông tin doanh thu.",
            "reason": "Chỉ nhân viên (staff) và quản trị viên (admin) mới có quyền này.",
            "your_role": user_role
        }
    
    return OrdersDB.get_revenue(period)
