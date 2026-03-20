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
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


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
    Lấy danh sách đơn hàng gần đây từ SQL Server kava_pos.dbo.hoa_don
    
    Permissions:
      - customer: allowed (public info)
      - staff, admin: allowed

    Queries SQL Server để lấy N hóa đơn gần nhất
    """
    try:
        from anthropic import Anthropic
        
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        
        # System prompt to generate SQL
        system_prompt = """You are a SQL Server expert. Convert this request to a T-SQL query ONLY.

Table: kava_pos.dbo.hoa_don with columns:
- id, ma_hoa_don, ten_khach_hang, so_dien_thoai, nhan_vien, cua_hang, dia_chi, ngay, tong_tien, trang_thai_thanh_toan, trang_thai_tra_hang

RULES:
1. 
2. Order by ngay DESC (newest first)
3. Only output SQL query, no markdown, no explanation"""
        
        # Generate SQL query
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": f"Get the {limit} most recent invoices"
                }
            ]
        )
        
        sql_query = response.content[0].text.strip()
        
        # Clean markdown if present
        if sql_query.startswith("```"):
            sql_query = sql_query.split("```")[1].split("```")[0].strip()
            if sql_query.startswith("sql"):
                sql_query = sql_query[3:].strip()
        
        print(f"   📝 SQL: {sql_query[:70]}...")
        
        # Execute SQL
        sql_api = "http://118.70.146.150:8888/api/public/execute"
        sql_response = requests.post(
            sql_api,
            headers={"Content-Type": "text/plain"},
            data=sql_query,
            timeout=10
        )
        
        if sql_response.status_code == 200:
            result = sql_response.json()
            
            if not result:
                return {"message": "Không có đơn hàng nào"}
            
            # Format for Claude
            orders = []
            for row in result:
                orders.append({
                    "ma_hoa_don": row.get("ma_hoa_don"),
                    "ten_khach_hang": row.get("ten_khach_hang"),
                    "so_dien_thoai": row.get("so_dien_thoai"),
                    "nhan_vien": row.get("nhan_vien"),
                    "cua_hang": row.get("cua_hang"),
                    "tong_tien": row.get("tong_tien"),
                    "trang_thai_thanh_toan": row.get("trang_thai_thanh_toan"),
                    "trang_thai_tra_hang": row.get("trang_thai_tra_hang"),
                    "ngay": row.get("ngay")
                })
            
            return {
                "total": len(orders),
                "orders": orders,
                "_debug": f"[SQL Query]\n{sql_query}"  # For logging to messages
            }
        else:
            return {"error": f"SQL error: {sql_response.status_code}"}
    
    except Exception as e:
        import traceback
        return {"error": f"Failed to fetch orders: {str(e)}", "trace": traceback.format_exc()}


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


# ─────────────────────────────────────────────
# Tool: get_invoice_stats
# ─────────────────────────────────────────────
def get_invoice_stats(stat_type: str = "total_revenue", user_role: str = "customer") -> Any:
    """
    Lấy thống kê hóa đơn từ SQL Server kava_pos database.
    
    Permissions:
      - customer: DENIED (business stats)
      - staff, admin: allowed
    
    Stat types:
      - total_revenue: Tổng doanh thu
      - total_paid: Tổng tiền chuyển khoản
      - invoice_count: Số lượng hóa đơn
      - avg_invoice: Trung bình giá trị hóa đơn
      - unpaid_count: Số hóa đơn chưa thanh toán
      - unreturned_count: Số hóa đơn chưa trả hàng
    """
    if not _check_permission(user_role, "internal"):
        return {
            "error": "Bạn không có quyền truy cập thông tin thống kê.",
            "reason": "Chỉ nhân viên (staff) và quản trị viên (admin) mới có quyền này.",
            "your_role": user_role
        }
    
    try:
        headers = {"Authorization": f"Bearer {AUTH_PASSWORD_MD5}"}
        response = requests.get(
            f"{API_BASE}/invoice-stats?stat_type={stat_type}",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"API error: {response.status_code}"}
    except Exception as e:
        return {"error": f"Failed to fetch invoice stats: {str(e)}"}


# ─────────────────────────────────────────────
# Tool: query_invoices (Dynamic Question → SQL)
# ─────────────────────────────────────────────
def query_invoices(question: str, user_role: str = "customer") -> Any:
    """
    Trả lời bất cứ câu hỏi nào về hóa đơn bằng cách:
    1. Dùng Claude để dịch câu hỏi tiếng Việt → SQL
    2. Chạy SQL trên SQL Server
    3. Trả về kết quả
    
    Permissions:
      - customer: DENIED (sensitive business data)
      - staff, admin: allowed
    
    Examples:
      - "Hóa đơn của Nguyễn A bao nhiêu tiền?"
      - "Danh sách nhân viên bán nhiều nhất"
      - "Hôm nay bán được bao nhiêu đơn?"
    """
    if not _check_permission(user_role, "internal"):
        return {
            "error": "Bạn không có quyền truy cập thông tin này.",
            "reason": "Chỉ nhân viên (staff) và quản trị viên (admin) mới có quyền.",
            "your_role": user_role
        }
    
    try:
        from anthropic import Anthropic
        
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        
        # DB Schema description
        db_schema = """Bảng: kava_pos.dbo.hoa_don
- id (bigint) - Primary key
- ma_hoa_don (bigint) - Invoice number
- ten_khach_hang (nvarchar 255) - Customer name
- so_dien_thoai (varchar 20) - Phone
- nhan_vien (nvarchar 255) - Staff name
- cua_hang (nvarchar 50) - Store name
- dia_chi (nvarchar 500) - Address
- ngay (datetime) - Order date
- link (ntext) - Invoice link
- dien_gia (ntext) - Description
- tien_ck (decimal) - Discount
- tong_tien (decimal) - Total amount
- tong_tien_chuyen_khoan (decimal) - Transferred amount
- trang_thai_thanh_toan (int) - Payment status (0=unpaid, 1=paid)
- trang_thai_tra_hang (int) - Return status (0=unreturned, 1=returned)
- ma_dat_coc (varchar 100) - Deposit code
- created_at (datetime)
- updated_at (datetime)"""
        
        # System prompt for converting question to SQL
        system_prompt = f"""You are a SQL Server expert. Convert Vietnamese questions to T-SQL queries ONLY.

{db_schema}

IMPORTANT:
1.
2. Use CAST(... AS DATE) for date comparisons
3. Only output the SQL query, no markdown, no explanation
4. Use kava_pos.dbo.hoa_don for table name
5. TODAY = CAST(GETDATE() AS DATE)

Output ONLY the SQL query, nothing else."""
        
        # Use Claude to generate SQL
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": question
                }
            ]
        )
        
        sql_query = response.content[0].text.strip()
        
        # Clean up markdown formatting if Claude returns it
        if sql_query.startswith("```sql"):
            sql_query = sql_query[6:]  # Remove ```sql
        if sql_query.startswith("```"):
            sql_query = sql_query[3:]  # Remove ```
        if sql_query.endswith("```"):
            sql_query = sql_query[:-3]  # Remove trailing ```
        sql_query = sql_query.strip()
        
        print(f"   📝 Generated SQL: {sql_query[:80]}...")
        
        # Execute SQL via remote API
        sql_api = "http://118.70.146.150:8888/api/public/execute"
        sql_response = requests.post(
            sql_api,
            headers={"Content-Type": "text/plain"},
            data=sql_query,
            timeout=10
        )
        
        if sql_response.status_code == 200:
            result = sql_response.json()
            print(f"   ✅ SQL executed, {len(result)} rows returned")
            return {
                "question": question,
                "sql": sql_query,
                "result": result,
                "_debug": f"[SQL Query]\n{sql_query}"  # For logging to messages
            }
        else:
            return {
                "error": f"SQL execution failed: {sql_response.status_code}",
                "details": sql_response.text,
                "sql": sql_query  # Keep SQL for debugging
            }
    
    except Exception as e:
        import traceback
        return {
            "error": f"Failed to process question: {str(e)}",
            "traceback": traceback.format_exc()
        }
