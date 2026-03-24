"""
Web server với authentication
Serve HTML + proxy API requests + CORS support
"""
import os
import sys
from dotenv import load_dotenv
from http.server import HTTPServer, SimpleHTTPRequestHandler
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
import urllib.parse
import json
import urllib.request

# Load environment variables
load_dotenv()

def get_config():
    """Load config from .env"""
    return {
        "AUTH_PASSWORD_MD5": os.getenv("AUTH_PASSWORD_MD5", "081904e6952d21450814cd3c465cf059"),
        "AUTH_COOKIE_DAYS": int(os.getenv("AUTH_COOKIE_DAYS", "30")),
    }

CONFIG = get_config()
AUTH_COOKIE_NAME = "bot_mvp_auth"

def verify_password(password: str) -> bool:
    """Verify password against MD5 hash"""
    password_hash = hashlib.md5(password.encode()).hexdigest()
    return password_hash == CONFIG["AUTH_PASSWORD_MD5"]

def get_login_html() -> str:
    """Return login page HTML"""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Super-AI-Erp - Login</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            background: linear-gradient(135deg, royalblue 0%, #4169e1 100%);
        }
        .login-box {
            background: white;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
            width: 100%;
            max-width: 400px;
        }
        .login-box h1 {
            text-align: center;
            color: #333;
            margin-bottom: 10px;
            font-size: 28px;
        }
        .login-box p {
            text-align: center;
            color: #999;
            margin-bottom: 30px;
            font-size: 14px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        .form-group label {
            display: block;
            margin-bottom: 8px;
            color: #333;
            font-weight: 500;
        }
        .form-group input {
            width: 100%;
            padding: 12px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
            transition: border-color 0.3s;
        }
        .form-group input:focus {
            outline: none;
            border-color: royalblue;
            box-shadow: 0 0 0 3px rgba(65, 105, 225, 0.1);
        }
        .btn {
            width: 100%;
            padding: 12px;
            background: linear-gradient(135deg, royalblue 0%, #4169e1 100%);
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, opacity 0.2s;
        }
        .btn:hover {
            transform: translateY(-2px);
            opacity: 0.9;
        }
        .btn:active {
            transform: translateY(0);
        }
        .error {
            background: #fff3cd;
            color: #856404;
            padding: 12px;
            border-radius: 6px;
            margin-bottom: 20px;
            display: none;
        }
        .remember {
            display: flex;
            align-items: center;
            font-size: 14px;
            color: #666;
            margin-top: 15px;
        }
        .remember input {
            margin-right: 8px;
            width: auto;
        }
    </style>
</head>
<body>
    <div class="login-box">
        <h1>Bot MVP</h1>
        <p>Secured Chat Interface</p>
        
        <form onsubmit="handleLogin(event)">
            <div id="error" class="error"></div>
            
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required autofocus>
            </div>
            
            <div class="remember">
                <input type="checkbox" id="remember" name="remember" checked>
                <label for="remember" style="margin: 0;">Remember me (30 days)</label>
            </div>
            
            <button type="submit" class="btn">Login</button>
        </form>
    </div>

    <script>
        function handleLogin(event) {
            event.preventDefault();
            const password = document.getElementById('password').value;
            const remember = document.getElementById('remember').checked;

            // Call web server's /auth endpoint which will:
            // 1. Verify password
            // 2. Set session cookie
            // 3. Call API /login to get token
            // 4. Return token to client
            const params = new URLSearchParams({
                password: password,
                remember: remember ? 'on' : 'off'
            });
            
            fetch('/auth', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: params.toString()
            })
            .then(r => {
                if (r.ok) return r.json();
                throw new Error('Invalid password');
            })
            .then(data => {
                // Save token from web server response
                if (data.token) {
                    localStorage.setItem('bot_api_token', data.token);
                }
                // Redirect to chat
                window.location.href = '/index.html';
            })
            .catch(e => {
                document.getElementById('error').textContent = 'Error: ' + e.message;
                document.getElementById('error').style.display = 'block';
            });
        }
    </script>
</body>
</html>"""

class CORSRequestHandler(SimpleHTTPRequestHandler):
    """HTTP handler với CORS + Auth support"""
    
    def end_headers(self):
        """Add CORS headers"""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, PUT, DELETE")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()
    
    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.end_headers()
    
    def check_auth(self) -> bool:
        """Check if request has valid auth cookie"""
        cookies = self.headers.get('Cookie', '')
        for cookie in cookies.split(';'):
            if AUTH_COOKIE_NAME in cookie:
                return True
        return False
    
    def do_GET(self):
        """Handle GET requests with auth"""
        clean_path = self.path.split('?')[0]
        
        # Public paths (no auth needed)
        public_paths = ['/', '/login.html', '/auth']
        
        # Check auth for protected pages
        if clean_path not in public_paths and not self.check_auth():
            self.send_response(302)
            self.send_header('Location', '/login.html')
            self.end_headers()
            return
        
        # Login page
        if clean_path == '/' or clean_path == '/login.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(get_login_html().encode('utf-8'))
            return
        
        # Serve app pages (after auth check)
        app_pages = ['/index.html', '/stats.html', '/docs.html', '/admin.html', '/messages.html', '/settings.html', '/db-admin.html', '/logs.html']
        if clean_path in app_pages:
            filename = clean_path.lstrip('/')
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                api_url = os.getenv("API_URL", "http://localhost:8100")
                api_port = os.getenv("API_PORT", "8100")
                content = content.replace('{{API_URL}}', api_url)
                content = content.replace('{{API_PORT}}', api_port)
                
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(content.encode('utf-8'))
                return
            except Exception as e:
                self.send_error(404, str(e))
                return
        
        # Static files - use parent class (SimpleHTTPRequestHandler)
        super().do_GET()
    
    def do_POST(self):
        """Handle POST requests (login)"""
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8')
        params = urllib.parse.parse_qs(post_data)
        
        if self.path == '/auth':
            password = params.get('password', [''])[0]
            remember = params.get('remember', [''])[0] == 'on'
            
            if not verify_password(password):
                self.send_response(401)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"error": "Invalid password"}')
                print("[AUTH] Failed login attempt")
                return
            
            # Get token from API server
            try:
                api_url = os.getenv("API_URL", "http://localhost:8100")
                login_url = f"{api_url}/login"
                
                # Call API to get token
                req_payload = json.dumps({"password": password}).encode('utf-8')
                req = urllib.request.Request(
                    login_url,
                    data=req_payload,
                    headers={'Content-Type': 'application/json'},
                    method='POST'
                )
                
                with urllib.request.urlopen(req, timeout=5) as response:
                    api_response = json.loads(response.read())
                    token = api_response.get('token', '')
                
                # Set auth cookie
                expiry_days = CONFIG["AUTH_COOKIE_DAYS"]
                expiry = datetime.now() + timedelta(days=expiry_days)
                cookie_value = f"{AUTH_COOKIE_NAME}=authenticated; Path=/; HttpOnly; SameSite=Lax"
                if remember:
                    cookie_value += f"; Expires={expiry.strftime('%a, %d %b %Y %H:%M:%S GMT')}"
                
                # Return success with token
                self.send_response(200)
                self.send_header('Set-Cookie', cookie_value)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response_data = json.dumps({
                    "status": "ok",
                    "token": token
                })
                self.wfile.write(response_data.encode('utf-8'))
                print(f"[AUTH] User logged in (cookie expires in {expiry_days} days)")
                
            except Exception as e:
                print(f"[AUTH] Error calling API /login: {e}")
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"API error: {str(e)}"}).encode('utf-8'))
                return
        
        else:
            # Other POST requests
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Custom logging"""
        print(f"[{self.client_address[0]}] {format % args}")

if __name__ == "__main__":
    web_host = os.getenv("WEB_HOST", "0.0.0.0")
    web_port = int(os.getenv("WEB_PORT"))
    web_url = os.getenv("WEB_URL")
    api_url = os.getenv("API_URL")
    
    # Change to web/ directory
    script_dir = Path(__file__).parent
    web_dir = script_dir / 'web'
    os.chdir(web_dir)
    
    server_address = (web_host, web_port)
    httpd = HTTPServer(server_address, CORSRequestHandler)
    
    print(f"\n{'='*50}")
    print(f"Bot MVP Web Server (with Authentication)")
    print(f"{'='*50}")
    print(f"Web URL:  {web_url}")
    print(f"Web Port: {web_port}")
    print(f"API URL:  {api_url}")
    print(f"Auth:     Enabled (password from .env)")
    print(f"Cookie:   {CONFIG['AUTH_COOKIE_DAYS']} days")
    print(f"{'='*50}\n")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Server stopped")
