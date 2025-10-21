#!/usr/bin/env python3
"""
HTTP Proxy Server - Forwards all HTTP requests to a target server
"""
import requests
from flask import Flask, request, Response
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configure target server
TARGET_HOST = "8.130.105.202"  # Change to target IP
TARGET_PORT = 8010         # Change to target port
TARGET_SCHEME = "http"     # http or https

TARGET_URL = f"{TARGET_SCHEME}://{TARGET_HOST}:{TARGET_PORT}"


@app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD'])
@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD'])
def proxy(path):
    """
    Proxy all requests to the target server
    """
    # Build target URL
    url = f"{TARGET_URL}/{path}"
    
    # Get request parameters
    params = request.args.to_dict()
    
    # Get request headers (exclude host header)
    headers = {key: value for key, value in request.headers if key.lower() != 'host'}
    
    # Get request body
    data = request.get_data()
    
    # Log request info
    logger.info(f"Forwarding {request.method} request to: {url}")
    logger.info(f"Query params: {params}")
    logger.info(f"Headers: {dict(headers)}")
    
    try:
        # Forward the request
        resp = requests.request(
            method=request.method,
            url=url,
            params=params,
            headers=headers,
            data=data,
            cookies=request.cookies,
            allow_redirects=False,
            stream=True
        )
        
        # Build response headers (exclude certain headers)
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        response_headers = [
            (name, value) for name, value in resp.raw.headers.items()
            if name.lower() not in excluded_headers
        ]
        
        # Create response
        response = Response(
            resp.content,
            status=resp.status_code,
            headers=response_headers
        )
        
        logger.info(f"Response status: {resp.status_code}")
        
        return response
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error forwarding request: {str(e)}")
        return Response(f"Proxy error: {str(e)}", status=502)


if __name__ == '__main__':
    # Run the proxy server
    """
    curl -X POST http://8.130.105.202:8010/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "Qwen3-8B",
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant."
            },
            {
                "role": "user", 
                "content": "你是谁？"
            }
        ]
    }'
    """
    PROXY_HOST = "0.0.0.0"  # Listen on all interfaces
    PROXY_PORT = 5010       # Proxy server port (must be different from target port!)
    
    logger.info(f"Starting HTTP Proxy Server on {PROXY_HOST}:{PROXY_PORT}")
    logger.info(f"Forwarding requests to {TARGET_URL}")
    
    app.run(
        host=PROXY_HOST,
        port=PROXY_PORT,
        debug=False,
        threaded=True
    )

