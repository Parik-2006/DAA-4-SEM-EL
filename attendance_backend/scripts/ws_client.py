import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import argparse

try:
    import websockets
except Exception:
    print("websockets library not installed. Install with: pip install websockets")
    raise


async def run(uri: str):
    async with websockets.connect(uri) as ws:
        print(f"Connected to {uri}")
        try:
            async for msg in ws:
                print("MSG:", msg)
        except websockets.ConnectionClosed as e:
            print("Connection closed", e)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--section", required=True)
    p.add_argument("--client", required=True)
    p.add_argument("--role", required=True)
    p.add_argument("--token", required=True)
    p.add_argument("--auth-token", required=False, help="Optional Bearer JWT for Authorization header")
    p.add_argument("--host", default="ws://127.0.0.1:8000")
    args = p.parse_args()

    # Build websocket URL with query params
    uri = f"{args.host}/api/v1/realtime/ws/{args.section}?client_id={args.client}&role={args.role}&token={args.token}&_token={args.token}"
    extra_headers = None
    if args.auth_token:
        extra_headers = [("Authorization", f"Bearer {args.auth_token}")]

    async def run_with_headers():
        async with websockets.connect(uri, extra_headers=extra_headers) as ws:
            print(f"Connected to {uri}")
            try:
                async for msg in ws:
                    print("MSG:", msg)
            except websockets.ConnectionClosed as e:
                print("Connection closed", e)

    asyncio.get_event_loop().run_until_complete(run_with_headers())


if __name__ == '__main__':
    main()
