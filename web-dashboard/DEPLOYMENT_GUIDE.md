# Web Dashboard Deployment Guide

## Quick Start

### Prerequisites
- Node.js 18+ installed
- npm or yarn package manager
- Backend API running (FastAPI server)
- Git repository (for Render deployment)

### Local Development

```bash
# 1. Navigate to web-dashboard directory
cd web-dashboard

# 2. Install dependencies
npm install

# 3. Create .env file with your configuration
cp .env.example .env

# 4. Update .env with your backend API URL
# VITE_API_BASE_URL=http://localhost:8000

# 5. Start development server
npm run dev
```

The dashboard will be available at `http://localhost:5173`

### Environment Variables

Create a `.env` file in the `web-dashboard` directory:

```env
# API Configuration
VITE_API_BASE_URL=http://your-backend-api.com
VITE_API_TIMEOUT=15000

# Polling Configuration (milliseconds)
VITE_POLLING_INTERVAL=5000

# Firebase (Optional - for real-time updates)
VITE_FIREBASE_API_KEY=your_api_key
VITE_FIREBASE_AUTH_DOMAIN=your_project.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your_project_id
VITE_FIREBASE_STORAGE_BUCKET=your_bucket
VITE_FIREBASE_MESSAGING_SENDER_ID=your_sender_id
VITE_FIREBASE_APP_ID=your_app_id

# Application Info
VITE_APP_NAME="Attendance Dashboard"
VITE_APP_VERSION="1.0.0"
```

### Build for Production

```bash
# Build the production bundle
npm run build

# Preview the production build locally
npm run preview
```

---

## Deployment on Render

Render is a free platform for hosting static sites and web services. Follow these steps:

### Step 1: Prepare GitHub Repository

1. Push your code to a public or private GitHub repository:

```bash
git add .
git commit -m "Add web dashboard with React, TypeScript, and Tailwind CSS"
git push origin main
```

2. Ensure `web-dashboard/` directory contains all necessary files

### Step 2: Create Render Account

1. Go to [render.com](https://render.com)
2. Click "Get Started" and sign up
3. Connect your GitHub account

### Step 3: Create New Web Service

1. Click "New +" button in Render dashboard
2. Select "Web Service"
3. Select your repository
4. Configure deployment:

**Basic Configuration:**
- **Name**: attendance-dashboard
- **Runtime**: Node
- **Region**: Select closest to your users (e.g., Singapore for Asia)
- **Branch**: main
- **Build Command**: `npm --prefix web-dashboard run build`
- **Start Command**: `npm --prefix web-dashboard run preview`
- **Plan**: Free (includes 750 free hours/month)

**Environment Variables:**
Click "Add Environment Variable" for each:

```
VITE_API_BASE_URL=https://your-backend-api.com
VITE_API_TIMEOUT=15000
VITE_POLLING_INTERVAL=5000
```

### Step 4: Configure Backend API URL

**Important:** The `VITE_API_BASE_URL` must be your deployed backend API URL, not localhost.

If your backend is also on Render:
```
VITE_API_BASE_URL=https://your-backend-name.onrender.com
```

If backend is on another platform (e.g., Railway, AWS):
```
VITE_API_BASE_URL=https://api.yourdomain.com
```

### Step 5: Deploy

1. Click "Create Web Service"
2. Render will automatically:
   - Pull your code from GitHub
   - Install dependencies
   - Build the application
   - Deploy to a live URL

3. Monitor deployment logs in the Render dashboard
4. Once complete, you'll get a public URL like: `https://attendance-dashboard.onrender.com`

### Step 6: Configure Custom Domain (Optional)

In Render dashboard:
1. Go to your service settings
2. Click "Custom Domain"
3. Add your domain (e.g., `dashboard.yourdomain.com`)
4. Update DNS records as instructed
5. SSL/TLS certificate auto-provisioned

---

## Docker Deployment

Deploy locally or on any Docker-capable server:

```bash
# Build Docker image
docker build -t attendance-dashboard .

# Run container
docker run -p 3000:3000 \
  -e VITE_API_BASE_URL=http://your-backend-api.com \
  attendance-dashboard

# Or use docker-compose
docker-compose up -d
```

---

## Monitoring & Debugging

### View Logs

**In Render:**
- Dashboard → Your Service → Logs tab
- Real-time logs show build and runtime errors

**Locally:**
```bash
npm run dev
# Logs appear in terminal
```

### Common Issues

**1. API Connection Failed**
- Check `VITE_API_BASE_URL` environment variable
- Verify backend API is running and accessible
- Check CORS configuration on backend

**2. Build Fails**
- Ensure all dependencies in `package.json`
- Check Node version compatibility (18+)
- Review build logs in Render

**3. Slow Performance**
- Increase `VITE_POLLING_INTERVAL` in .env
- Check network latency to backend
- Review API response times

---

## Performance Optimization

### Frontend Optimization
- Vite automatically bundles and minifies code
- CSS is tree-shaken for minimal bundle size
- Images/assets are optimized during build

### Backend Integration
- Adjust polling interval based on server load
- Use course filtering to reduce data transfer
- Implement pagination for large datasets

### Network Optimization
- Use CDN for static assets (Render provides this)
- Enable compression on backend (GZIP)
- Use WebSockets for real-time instead of polling (future enhancement)

---

## Security Considerations

### API Security
- Never commit `.env` files with real credentials
- Use environment variables for sensitive data
- Enable HTTPS (auto-enabled on Render)
- Implement CORS properly on backend

### Authentication
- Implement JWT token-based auth
- Store tokens securely (httpOnly cookies)
- Auto-refresh tokens before expiration
- Clear tokens on logout

---

## Troubleshooting

### Dashboard Shows "System Offline"

1. Check backend is running:
```bash
curl https://your-backend-api.com/api/v1/health
```

2. Verify environment variable is correct in Render
3. Check backend CORS settings

### Data Not Updating

1. Verify polling interval in .env (default 5000ms)
2. Check browser console for API errors (F12)
3. Verify course selection/filtering logic

### Build Fails on Render

1. Check Node.js version (requires 18+)
2. Ensure all dependencies are in package.json
3. Review build logs for specific errors
4. Check free tier resource limits

---

## Maintenance

### Update Dependencies
```bash
npm update
npm audit
```

### Check for Security Vulnerabilities
```bash
npm audit fix
```

### Redeploy After Changes
```bash
git push origin main
# Render auto-redeploys on push
```

---

## Support & Resources

- **Render Docs**: https://render.com/docs
- **React Docs**: https://react.dev
- **Tailwind CSS**: https://tailwindcss.com
- **Vite**: https://vitejs.dev

---

## Next Steps

1. ✅ Deploy web dashboard on Render
2. ⏳ Configure backend API connection
3. ⏳ Set up custom domain
4. ⏳ Enable Firebase real-time (optional)
5. ⏳ Monitor performance and optimize as needed
