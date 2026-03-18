/**
 * Configuration file for Bot MVP
 * 
 * Customize port settings here if needed
 * (This is optional - index.html auto-detects API URL)
 */

// API Configuration
const CONFIG = {
    // API Server
    api: {
        host: "localhost",
        port: 8000,
        get url() {
            return `http://${this.host}:${this.port}`;
        }
    },
    
    // Web Server (for reference)
    web: {
        host: "localhost", 
        port: 8080,
        get url() {
            return `http://${this.host}:${this.port}`;
        }
    },
    
    // Debug logging
    debug: true
};

// Log config on load
if (CONFIG.debug) {
    console.log("📋 Bot MVP Config:", CONFIG);
    console.log("🤖 API URL:", CONFIG.api.url);
    console.log("💻 Web URL:", CONFIG.web.url);
}
