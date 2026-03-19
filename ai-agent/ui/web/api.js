/**
 * api.js - Centralized API helper with automatic authentication
 * 
 * Usage:
 *   const data = await apiCall('/chat', 'POST', {message: 'Hello'});
 *   const users = await apiCall('/users', 'GET');
 *   await apiCall('/docs/123', 'DELETE');
 */

const API_PORT = "{{API_PORT}}".includes('{{') ? "8100" : "{{API_PORT}}";
const API_BASE = "{{API_URL}}".includes('{{') ? `http://${window.location.hostname}:${API_PORT}` : "{{API_URL}}";

/**
 * Get authorization headers with Bearer token from localStorage
 */
function getAuthHeaders(additionalHeaders = {}) {
  const token = localStorage.getItem('bot_api_token') || '';
  const headers = { 
    'Content-Type': 'application/json',
    ...additionalHeaders 
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

/**
 * Make authenticated API call
 * @param {string} endpoint - API endpoint (e.g., '/chat', '/users')
 * @param {string} method - HTTP method (GET, POST, PUT, DELETE)
 * @param {object} body - Request body (optional, for POST/PUT/DELETE)
 * @param {object} queryParams - URL query parameters (optional)
 * @param {object} additionalHeaders - Extra headers to add (optional)
 * @returns {Promise<object>} Response JSON
 */
async function apiCall(endpoint, method = 'GET', body = null, queryParams = null, additionalHeaders = {}) {
  let url = API_BASE + endpoint;
  
  // Add query parameters if provided
  if (queryParams && Object.keys(queryParams).length > 0) {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(queryParams)) {
      if (value !== null && value !== undefined) {
        params.append(key, value);
      }
    }
    url += '?' + params.toString();
  }
  
  const options = {
    method,
    headers: getAuthHeaders(additionalHeaders),
  };
  
  // Add body for POST/PUT/DELETE if provided
  if (body && (method === 'POST' || method === 'PUT' || method === 'DELETE' || method === 'PATCH')) {
    if (body instanceof FormData) {
      // For FormData, don't set Content-Type (browser will set it with boundary)
      delete options.headers['Content-Type'];
      options.body = body;
    } else {
      options.body = JSON.stringify(body);
    }
  }
  
  try {
    const response = await fetch(url, options);
    
    // Handle non-JSON responses (e.g., plain text)
    const contentType = response.headers.get('content-type');
    let data;
    
    if (contentType && contentType.includes('application/json')) {
      data = await response.json();
    } else {
      data = await response.text();
    }
    
    // Check for errors
    if (!response.ok) {
      const error = new Error(data?.detail || data?.error || response.statusText);
      error.status = response.status;
      error.response = data;
      throw error;
    }
    
    return data;
  } catch (error) {
    console.error(`API Error [${method} ${endpoint}]:`, error);
    throw error;
  }
}

/**
 * Convenience methods for common operations
 */
const api = {
  get: (endpoint, queryParams = null, headers = {}) => 
    apiCall(endpoint, 'GET', null, queryParams, headers),
  
  post: (endpoint, body, queryParams = null, headers = {}) => 
    apiCall(endpoint, 'POST', body, queryParams, headers),
  
  put: (endpoint, body, queryParams = null, headers = {}) => 
    apiCall(endpoint, 'PUT', body, queryParams, headers),
  
  delete: (endpoint, body = null, queryParams = null, headers = {}) => 
    apiCall(endpoint, 'DELETE', body, queryParams, headers),
  
  patch: (endpoint, body, queryParams = null, headers = {}) => 
    apiCall(endpoint, 'PATCH', body, queryParams, headers),
};

// Export for use
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { apiCall, api, getAuthHeaders };
}
