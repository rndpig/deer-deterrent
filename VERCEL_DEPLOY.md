# Vercel Deployment Guide

## Prerequisites

1. **Make GitHub repository public**
   ```bash
   # Go to GitHub > Settings > Change repository visibility > Make public
   ```

2. **Get Google OAuth credentials**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing
   - Enable Google+ API
   - Go to "Credentials" → "Create Credentials" → "OAuth 2.0 Client ID"
   - Application type: "Web application"
   - Authorized redirect URIs:
     - `https://deer.rndpig.com/api/auth/callback`
     - `http://localhost:5173/api/auth/callback` (for local testing)
   - Save the Client ID and Client Secret

## Step 1: Deploy to Vercel

1. **Connect to Vercel**
   - Go to [vercel.com](https://vercel.com)
   - Click "Add New Project"
   - Import `rndpig/deer-deterrent` repository
   - **Root Directory**: Set to `frontend`

2. **Configure Environment Variables**

   Add these environment variables in Vercel dashboard:

   ```
   GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=your-google-client-secret
   VITE_API_URL=http://localhost:8000
   ```

   Note: `VITE_API_URL` will be updated later when backend is deployed to QNAP

3. **Deploy**
   - Click "Deploy"
   - Wait for build to complete
   - Vercel will assign a URL like `deer-deterrent-abc123.vercel.app`

## Step 2: Configure Custom Domain

1. **Add Custom Domain in Vercel**
   - Project Settings → Domains
   - Add `deer.rndpig.com`

2. **Update DNS in Cloudflare**
   - Go to Cloudflare dashboard
   - DNS → Add record:
     - Type: `CNAME`
     - Name: `deer`
     - Target: `cname.vercel-dns.com`
     - Proxy status: DNS only (gray cloud)
   - Save

3. **Wait for DNS propagation** (usually 5-10 minutes)

4. **Verify**
   - Visit https://deer.rndpig.com
   - Should see Google sign-in page

## Step 3: Update Google OAuth

1. **Add production redirect URI**
   - Go back to Google Cloud Console
   - Credentials → Edit OAuth client
   - Add authorized redirect URI:
     - `https://deer.rndpig.com/api/auth/callback`
   - Save

## Step 4: Test Authentication

1. Visit https://deer.rndpig.com
2. Click "Sign in with Google"
3. Select rndpig@gmail.com account
4. Should redirect back to dashboard
5. Try logging in with a different email - should see "Access Denied" message

## Step 5: Connect to Backend (Later)

Once your backend is deployed on QNAP with Cloudflare Tunnel:

1. Update `VITE_API_URL` environment variable in Vercel:
   ```
   VITE_API_URL=https://deer-api.rndpig.com
   ```

2. Redeploy (Vercel auto-deploys on env var changes)

## Troubleshooting

### "Access Denied" for rndpig@gmail.com

- Check the `allowedEmail` in `frontend/api/auth/[...action].js`
- Should be exactly `rndpig@gmail.com`
- Redeploy if you made changes

### OAuth Error

- Verify redirect URIs in Google Cloud Console match exactly
- Check that both HTTP and HTTPS variants are added
- Make sure Google+ API is enabled

### Can't connect to backend

- Backend URL must be HTTPS (Cloudflare Tunnel provides this)
- Check CORS settings in backend allow `https://deer.rndpig.com`
- Verify backend is running and accessible

### Session not persisting

- Check browser allows cookies
- Verify `SameSite` and `Secure` cookie attributes
- Try in incognito mode to rule out extensions

## Security Notes

- ✅ Only rndpig@gmail.com can access the application
- ✅ Sessions expire after 30 days
- ✅ HTTPS enforced by Vercel
- ✅ OAuth flow handled securely server-side
- ✅ No sensitive data stored client-side

## Local Development with OAuth

To test OAuth locally:

1. Make sure `http://localhost:5173/api/auth/callback` is in Google OAuth allowed redirects

2. Start local dev server:
   ```bash
   cd frontend
   npm run dev
   ```

3. Visit http://localhost:5173
4. OAuth should work with local server

## Continuous Deployment

Every push to `main` branch automatically deploys to Vercel!

Just commit and push:
```bash
git add .
git commit -m "Update frontend"
git push
```

Vercel will build and deploy within 1-2 minutes.
