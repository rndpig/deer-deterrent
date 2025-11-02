# Deployment Checklist

## ✅ Pre-Deployment

- [x] Code committed and pushed to GitHub
- [ ] **Make repository public** (required for Vercel free tier)
  - Go to: https://github.com/rndpig/deer-deterrent/settings
  - Scroll to "Danger Zone"
  - Click "Change visibility" → "Make public"
  - Confirm

## 🔐 Google OAuth Setup

- [ ] Go to [Google Cloud Console](https://console.cloud.google.com/)
- [ ] Create new project or select existing
- [ ] Enable Google+ API
- [ ] Create OAuth 2.0 Client ID:
  - Application type: Web application
  - Name: Deer Deterrent
  - Authorized redirect URIs:
    - `https://deer.rndpig.com/api/auth/callback`
    - `http://localhost:5173/api/auth/callback`
- [ ] Save Client ID and Client Secret (you'll need these for Vercel)

## 🚀 Vercel Deployment

- [ ] Go to [vercel.com](https://vercel.com) and sign in
- [ ] Click "Add New Project"
- [ ] Import `rndpig/deer-deterrent`
- [ ] **IMPORTANT**: Set Root Directory to `frontend`
- [ ] Add environment variables:
  ```
  GOOGLE_CLIENT_ID=your-client-id-here.apps.googleusercontent.com
  GOOGLE_CLIENT_SECRET=your-client-secret-here
  VITE_API_URL=http://localhost:8000
  ```
- [ ] Click "Deploy"
- [ ] Wait for build to complete

## 🌐 Custom Domain Setup

- [ ] In Vercel: Project Settings → Domains → Add `deer.rndpig.com`
- [ ] In Cloudflare DNS:
  - Type: CNAME
  - Name: deer
  - Target: cname.vercel-dns.com
  - Proxy: OFF (gray cloud)
- [ ] Wait 5-10 minutes for DNS propagation
- [ ] Verify: https://deer.rndpig.com should load

## 🔒 Update OAuth for Production

- [ ] Go back to Google Cloud Console
- [ ] Edit OAuth client
- [ ] Verify redirect URI is added:
  - `https://deer.rndpig.com/api/auth/callback`
- [ ] Save

## ✨ Test Deployment

- [ ] Visit https://deer.rndpig.com
- [ ] Should see login screen
- [ ] Click "Sign in with Google"
- [ ] Sign in with rndpig@gmail.com
- [ ] Should see dashboard
- [ ] Try signing in with different email - should see "Access Denied"
- [ ] Sign out button should work
- [ ] Refresh page - should stay logged in (session persists)

## 🎯 Next Steps (Optional - After Backend Deployed)

- [ ] Deploy backend to QNAP with Docker
- [ ] Set up Cloudflare Tunnel for backend (deer-api.rndpig.com)
- [ ] Update Vercel environment variable:
  ```
  VITE_API_URL=https://deer-api.rndpig.com
  ```
- [ ] Redeploy frontend
- [ ] Test full integration

## 📝 Notes

- Vercel auto-deploys on every push to `main` branch
- Only rndpig@gmail.com can access the app
- Backend URL can stay as localhost until QNAP deployment ready
- OAuth works even without backend running
- Sessions last 30 days

## 🆘 If Something Goes Wrong

See `VERCEL_DEPLOY.md` for detailed troubleshooting guide.
