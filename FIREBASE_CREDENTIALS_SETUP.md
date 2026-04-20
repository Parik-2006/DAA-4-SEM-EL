## Firebase Service Account Setup

### ⚠️ IMPORTANT: Keep Your Credentials Secure

Your Firebase service account key contains sensitive information that should **NEVER** be committed to version control or shared publicly.

### Setup Instructions

#### 1. **Download Your Firebase Service Account Key**

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select your project (**daa-4th-sem**)
3. Click **Project Settings** (gear icon) → **Service Accounts** tab
4. Under **Firebase Admin SDK**, click **Generate New Private Key**
5. A JSON file (`daa-4th-sem-firebase-adminsdk-xxxxx.json`) will download

#### 2. **Place the Credentials File**

Copy the downloaded file to your backend:
```bash
cp ~/Downloads/daa-4th-sem-firebase-adminsdk-xxxxx.json attendance_backend/config/firebase-credentials.json
```

#### 3. **Verify It's Ignored**

Make sure `.gitignore` contains:
```
config/firebase-credentials.json
firebase-credentials.json
```

Check it's not tracked:
```bash
git status --ignored
```

#### 4. **Update Your .env File**

Ensure `attendance_backend/.env` or root `.env` has:
```env
FIREBASE_CREDENTIALS_PATH=config/firebase-credentials.json
FIREBASE_PROJECT_ID=daa-4th-sem
FIREBASE_DATABASE_URL=https://daa-4th-sem.firebaseio.com
FIREBASE_STORAGE_BUCKET=daa-4th-sem.appspot.com
```

#### 5. **Test the Connection**

```bash
cd attendance_backend
python -c "from config.settings import get_settings; s = get_settings(); print('Credentials path:', s.get_credentials_path())"
```

### ✅ Deployment Checklist

- ✅ **Never commit** `firebase-credentials.json` to Git
- ✅ **Add to `.gitignore`** if not already there
- ✅ **Use environment variables** for production deployments
- ✅ **Store in secure vault** (e.g., GitHub Secrets, AWS Secrets Manager) for CI/CD
- ✅ **Rotate credentials** if ever exposed
- ✅ **Use different keys** for development, staging, and production

### 🚀 For CI/CD Deployment

When deploying to production servers or Docker containers:

**Option 1: GitHub Secrets (Recommended)**
```bash
# In your GitHub Actions workflow:
- name: Create Firebase Credentials
  run: |
    echo '${{ secrets.FIREBASE_CREDENTIALS_JSON }}' > attendance_backend/config/firebase-credentials.json
```

**Option 2: Environment Variables**
```bash
# Convert credentials to base64 and store as secret
cat firebase-credentials.json | base64 > credentials.b64

# In deployment script:
echo $FIREBASE_CREDENTIALS_B64 | base64 -d > config/firebase-credentials.json
```

### 📋 What's Already Configured

✅ Backend (`attendance_backend/config/firebase_client.py`) properly loads credentials  
✅ `.env.example` and `.env` reference the credentials path  
✅ `.gitignore` protects all `firebase-credentials.json` files  
✅ Settings module validates credentials on startup  

### 🔒 Security Best Practices

1. **Restrict Key Permissions**: In Firebase Console, limit service account permissions
2. **Monitor Usage**: Check Firebase Console for unusual activity
3. **Rotate Keys Regularly**: Delete old keys and generate new ones
4. **Use Different Projects**: Development ≠ Production credentials
5. **Alert on Exposure**: Enable GitHub Secret Scanning alerts

---

**After placing credentials locally, your backend can:**
- ✅ Read/write from Firestore
- ✅ Access Firebase Storage
- ✅ Manage user authentication
- ✅ Create attendance records
- ✅ Store face embeddings
