# Bot MVP - UI Setup Guide

Tất cả các files từ MVP-bot-api đã được copy sang folder này. Bây giờ bạn có thể chạy bot từ đây một cách độc lập.

## Cấu trúc thư mục

```
ui/
├── api.py              # FastAPI server (main API)
├── web_server.py       # Web server (serve HTML)
├── bot.py              # Claude bot logic
├── database.py         # SQLite database manager
├── memory.py           # User memory management
├── rag.py              # RAG (document retrieval)
├── embeddings.py       # Embedding model
├── skills.py           # Bot tools/skills
├── data_provider.py    # Data access layer
├── docs_api.py         # Document management API
├── doc_processor.py    # Document processing
├── utils.py            # Utility functions
├── .env                # Environment variables
├── requirements.txt    # Python dependencies
├── web/                # Static HTML/CSS/JS files
│   ├── index.html     # Main chat interface
│   ├── stats.html     # Statistics page
│   ├── admin.html     # Admin panel
│   ├── messages.html  # Messages panel
│   ├── style.css      # Shared styles
│   ├── config.js      # Configuration
│   └── nav.js         # Navigation script
└── uploads/            # Uploaded documents storage
```

## Hướng dẫn cài đặt & chạy

### 1. Cài đặt dependencies

```bash
# Từ folder ui/
pip install -r requirements.txt
```

### 2. Kiểm tra .env file

Mở `.env` và đảm bảo:
- `ANTHROPIC_API_KEY` đã được set
- Các port không bị chiếm (mặc định: API=8100, Web=8080)

### 3. Khởi động API Server

```bash
python api.py
```

API sẽ chạy trên: `http://localhost:8100`

### 4. Khởi động Web Server (trong terminal khác)

```bash
python web_server.py
```

Web sẽ phục vụ tại: `http://localhost:8080`

### 5. Truy cập ứng dụng

- **Chat Interface**: http://localhost:8080/index.html
- **API Docs**: http://localhost:8100/docs
- **Stats**: http://localhost:8080/stats.html
- **Admin**: http://localhost:8080/admin.html

## Cấu hình

### Ports
- `API_PORT=8100` - FastAPI server
- `WEB_PORT=8080` - Web server

Nếu cần thay đổi, sửa trong `.env` file.

### Claude Model
Mặc định sử dụng `claude-3-haiku-20240307` (nhanh, rẻ).

Để thay đổi, sửa `CLAUDE_MODEL` trong `.env`:
```env
# Options:
CLAUDE_MODEL=claude-sonnet-4-20250514      # Best quality (expensive)
CLAUDE_MODEL=claude-3-7-sonnet-20250219    # Balance
CLAUDE_MODEL=claude-3-haiku-20240307       # Fast & cheap
```

### Timezone
Mặc định: `UTC+7` (Asia/Ho_Chi_Minh)

Để thay đổi, sửa `TZ_OFFSET_HOURS` trong `.env`.

## Database

Mỗi lần chạy, `database.py` sẽ tự động:
- Tạo `bot_data.db` nếu chưa tồn tại
- Seed default categories, roles, users

Để xóa tất cả dữ liệu: xóa file `bot_data.db`

## Troubleshooting

### API không kết nối được
1. Kiểm tra `ANTHROPIC_API_KEY` trong `.env`
2. Kiểm tra port 8100 không bị chiếm: `netstat -an | findstr 8100`
3. Chạy API lại: `python api.py`

### Web server không load  
1. Kiểm tra port 8080 không bị chiếm
2. Chạy web server lại: `python web_server.py`

### Database error
- Xóa `bot_data.db` để reset
- Chạy lại API server

## Tính năng chính

✅ Chat interface với Claude 3  
✅ Long-term user memory  
✅ RAG (document retrieval)  
✅ Multi-user support với role-based access  
✅ Document management (upload, process, embed)  
✅ Usage tracking & statistics  
✅ Admin dashboard  
✅ Tool-use & function calling  

## API Endpoints

```
POST   /chat                    - Send message
GET    /health                  - Health check
GET    /stats                   - Usage statistics
GET    /conversations/{id}      - Get conversation history
GET    /messages/user/{user_id} - Get user messages
POST   /docs/upload             - Upload document
GET    /docs/list               - List documents
```

## Notes

- Database sử dụng **SQLite** (file `bot_data.db`)
- Embeddings sử dụng **MiniLM multilingual** model (~420MB, tự download)
- Documents được store trong folder `uploads/`
- Static files (HTML/JS/CSS) trong folder `web/`

---

Chúc bạn sử dụng thành công! 🚀
