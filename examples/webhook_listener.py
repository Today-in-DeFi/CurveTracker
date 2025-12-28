#!/usr/bin/env python3
"""
Example: Webhook Listener for Pool Additions

Shows how to create a simple HTTP server that accepts pool addition requests.
Useful for integrating with other services or alerting systems.

Usage:
    python3 webhook_listener.py

Then POST to http://localhost:8080/add-pool with JSON:
    {
        "chain": "ethereum",
        "pool": "0xabc...",
        "comment": "New high-yield pool",
        "stakedao_enabled": true,
        "beefy_enabled": true
    }
"""

import sys
import os
import json
from http.server import HTTPServer, BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pool_manager import PoolManager


class PoolWebhookHandler(BaseHTTPRequestHandler):
    """Handle webhook requests for pool management"""

    def do_POST(self):
        """Handle POST requests"""
        if self.path == '/add-pool':
            self.add_pool()
        elif self.path == '/remove-pool':
            self.remove_pool()
        elif self.path == '/list-pools':
            self.list_pools()
        else:
            self.send_error(404, "Endpoint not found")

    def add_pool(self):
        """Add a pool via webhook"""
        try:
            # Read request body
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)
            data = json.loads(body)

            # Validate required fields
            if 'chain' not in data or 'pool' not in data:
                self.send_error(400, "Missing required fields: chain, pool")
                return

            # Add pool
            manager = PoolManager()
            success = manager.add_pool(
                chain=data['chain'],
                pool=data['pool'],
                comment=data.get('comment'),
                stakedao_enabled=data.get('stakedao_enabled'),
                beefy_enabled=data.get('beefy_enabled'),
                validate=data.get('validate', True)
            )

            # Send response
            response = {
                'success': success,
                'message': 'Pool added' if success else 'Pool already exists or validation failed'
            }

            self.send_response(200 if success else 409)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
        except Exception as e:
            self.send_error(500, str(e))

    def remove_pool(self):
        """Remove a pool via webhook"""
        try:
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)
            data = json.loads(body)

            if 'chain' not in data or 'pool' not in data:
                self.send_error(400, "Missing required fields: chain, pool")
                return

            manager = PoolManager()
            success = manager.remove_pool(data['chain'], data['pool'])

            response = {
                'success': success,
                'message': 'Pool removed' if success else 'Pool not found'
            }

            self.send_response(200 if success else 404)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

        except Exception as e:
            self.send_error(500, str(e))

    def list_pools(self):
        """List all pools via webhook"""
        try:
            manager = PoolManager()
            pools = manager.list_pools()

            response = {
                'success': True,
                'pools': pools,
                'count': len(pools)
            }

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response, indent=2).encode())

        except Exception as e:
            self.send_error(500, str(e))


def main():
    PORT = 8080

    print(f"🚀 Starting webhook listener on port {PORT}...")
    print(f"\nAvailable endpoints:")
    print(f"  POST http://localhost:{PORT}/add-pool")
    print(f"  POST http://localhost:{PORT}/remove-pool")
    print(f"  POST http://localhost:{PORT}/list-pools")
    print(f"\nPress Ctrl+C to stop")

    server = HTTPServer(('', PORT), PoolWebhookHandler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down webhook listener")
        server.shutdown()


if __name__ == "__main__":
    main()
