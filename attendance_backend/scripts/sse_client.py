#!/usr/bin/env python
"""SSE client for real-time attendance updates."""

import sys
import argparse
import requests


def main():
    """Connect to SSE endpoint and stream updates."""
    parser = argparse.ArgumentParser(description="SSE client for attendance updates")
    parser.add_argument("--section", required=True, help="Section ID")
    parser.add_argument("--client", required=True, help="Client ID")
    parser.add_argument("--role", required=True, help="User role")
    parser.add_argument("--token", required=True, help="Route-level token (RTDB or dev_ token)")
    parser.add_argument("--auth-token", required=False, help="Middleware JWT for _token param")
    parser.add_argument("--host", default="http://127.0.0.1:8000", help="API host")
    
    args = parser.parse_args()

    # Use auth-token if provided, otherwise fall back to token
    auth_token = args.auth_token or args.token
    
    # Build SSE URL
    url = (
        f"{args.host}/api/v1/realtime/sse/{args.section}"
        f"?client_id={args.client}&role={args.role}"
        f"&token={args.token}&_token={auth_token}"
    )
    
    print(f"Connecting to SSE: {url}")
    
    try:
        with requests.get(url, stream=True, timeout=30) as response:
            if response.status_code != 200:
                print(f"Failed to connect: {response.status_code} {response.text}")
                return 1
            
            print("Connected. Listening for updates...")
            for line in response.iter_lines(decode_unicode=True):
                if line:
                    print(line)
    
    except requests.exceptions.Timeout:
        print("Connection timeout")
        return 1
    except requests.exceptions.ConnectionError as e:
        print(f"Connection error: {e}")
        return 1
    except KeyboardInterrupt:
        print("\nConnection closed by user")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
