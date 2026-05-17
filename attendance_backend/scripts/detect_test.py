import sys
import os
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def main():
    host = 'http://127.0.0.1:8000'
    img = os.path.join(os.path.dirname(__file__), '..', 'test_data', 'student_photos', 'student_001', 'photo_001.jpg')
    img = os.path.abspath(img)
    if not os.path.exists(img):
        print('Test image not found:', img)
        return

    # Use JWT for middleware and dev token for route-level
    from scripts.create_token import AuthService  # fallback, not used if import fails
    # Instead reuse the token we can generate via create_token script externally
    # For now accept token from env or create a JWT
    token = os.environ.get('TEST_JWT')
    if not token:
        # try to import AuthService
        try:
            from services.auth_service import AuthService
            svc = AuthService()
            token = svc.create_token(user_id='teacher1', email='teacher@local', role='teacher', assigned_sections=['TEST_SECTION'])
        except Exception:
            print('No TEST_JWT env and failed to construct one; set TEST_JWT to proceed')
            return

    files = {'file': open(img, 'rb')}
    params = {'_token': token}
    url = f"{host}/api/v1/attendance/detect-face-only"
    print('POST', url)
    r = requests.post(url, files=files, params=params)
    print('Status:', r.status_code)
    try:
        print(r.json())
    except Exception:
        print(r.text)

if __name__ == '__main__':
    main()
