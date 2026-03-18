"""
Simple web server để serve HTML + proxy API requests
Giải quyết CORS issues
"""
import os
from dotenv import load_dotenv
from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
from pathlib import Path

# Load environment variables
load_dotenv()

class CORSRequestHandler(SimpleHTTPRequestHandler):
    """HTTP handler với CORS support"""
    
    def end_headers(self):
        """Thêm CORS headers"""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, PUT, DELETE")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()
    
    def do_OPTIONS(self):
        """Handle OPTIONS requests (CORS preflight)"""
        self.send_response(200)
        self.end_headers()
    
    def do_GET(self):
        """Override GET to inject API_URL into index.html"""
        # Strip query params for path comparison
        clean_path = self.path.split('?')[0]
        print(f"🔍 do_GET path='{self.path}' clean='{clean_path}'")
        
        if clean_path == '/' or clean_path == '/index.html' or clean_path == '/stats.html' or clean_path == '/docs.html' or clean_path == '/admin.html' or clean_path == '/messages.html' or clean_path == '/settings.html':
            if clean_path == '/stats.html':
                filename = 'stats.html'
            elif clean_path == '/docs.html':
                filename = 'docs.html'
            elif clean_path == '/admin.html':
                filename = 'admin.html'
            elif clean_path == '/messages.html':
                filename = 'messages.html'
            elif clean_path == '/settings.html':
                filename = 'settings.html'
            else:
                filename = 'index.html'
            # Read html file and inject API_URL from .env
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                
                # Replace placeholders with values from .env
                api_url = os.getenv("API_URL", "http://localhost:8100")
                api_port = os.getenv("API_PORT", "8100")
                print(f"🔌 Injecting API_URL='{api_url}' API_PORT='{api_port}' into {filename}")

                html_content = html_content.replace('{{API_URL}}', api_url)
                html_content = html_content.replace('{{API_PORT}}', api_port)
                
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(html_content.encode('utf-8'))
                return
            except Exception as e:
                print(f"Error reading {filename}: {e}")
        
        # Default behavior for other files
        super().do_GET()
    
    def log_message(self, format, *args):
        """Custom logging"""
        print(f"[{self.client_address[0]}] {format % args}")

if __name__ == "__main__":
    # Get config from .env
    web_host = os.getenv("WEB_HOST", "0.0.0.0")
    web_port = int(os.getenv("WEB_PORT"))
    web_url = os.getenv("WEB_URL")
    api_url = os.getenv("API_URL")
    
    # Change to web/ directory so static files are served from there
    script_dir = Path(__file__).parent
    web_dir = script_dir / 'web'
    os.chdir(web_dir)
    
    server_address = (web_host, web_port)
    httpd = HTTPServer(server_address, CORSRequestHandler)
    
    print(f"\n{'='*50}")
    print(f"💻 Bot MVP Web Server")
    print(f"{'='*50}")
    print(f"🌐 Web URL: {web_url}/index.html")
    print(f"🔌 Port: {web_port}")
    print(f"🤖 API URL: {api_url}")
    print(f"📁 Directory: {web_dir}")
    print(f"\n⚠️  Chắc chắn API server chạy trên {api_url}")
    print(f"{'='*50}")
    print(f"Nhấn Ctrl+C để tắt server\n")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n✅ Server đã tắt")
