const allowedEmail = 'rndpig@gmail.com';

export default async function handler(req, res) {
  // Set CORS headers
  res.setHeader('Access-Control-Allow-Credentials', 'true');
  res.setHeader('Access-Control-Allow-Origin', req.headers.origin || '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET,POST,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  const { action } = req.query;

  // Session store (in production, use a database)
  const session = req.cookies?.['deer-session'];

  if (action === 'session') {
    // Check session
    if (session) {
      try {
        const userData = JSON.parse(Buffer.from(session, 'base64').toString());
        if (userData.email === allowedEmail) {
          return res.status(200).json({ user: userData });
        }
      } catch (error) {
        console.error('Session parse error:', error);
      }
    }
    return res.status(200).json({ user: null });
  }

  if (action === 'signin') {
    // Google OAuth redirect
    const clientId = process.env.GOOGLE_CLIENT_ID;
    const redirectUri = `${process.env.VERCEL_URL || req.headers.origin}/api/auth/callback`;
    const googleAuthUrl = `https://accounts.google.com/o/oauth2/v2/auth?` +
      `client_id=${clientId}&` +
      `redirect_uri=${encodeURIComponent(redirectUri)}&` +
      `response_type=code&` +
      `scope=email profile&` +
      `access_type=offline`;
    
    return res.redirect(302, googleAuthUrl);
  }

  if (action === 'callback') {
    // Handle Google OAuth callback
    const { code } = req.query;
    
    if (!code) {
      return res.redirect(302, '/?error=no_code');
    }

    try {
      // Exchange code for tokens
      const tokenResponse = await fetch('https://oauth2.googleapis.com/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
          code,
          client_id: process.env.GOOGLE_CLIENT_ID,
          client_secret: process.env.GOOGLE_CLIENT_SECRET,
          redirect_uri: `${process.env.VERCEL_URL || req.headers.origin}/api/auth/callback`,
          grant_type: 'authorization_code',
        }),
      });

      const tokens = await tokenResponse.json();

      if (!tokens.access_token) {
        return res.redirect(302, '/?error=no_token');
      }

      // Get user info
      const userResponse = await fetch('https://www.googleapis.com/oauth2/v2/userinfo', {
        headers: { Authorization: `Bearer ${tokens.access_token}` },
      });

      const userData = await userResponse.json();

      // Check if user is authorized
      if (userData.email !== allowedEmail) {
        return res.redirect(302, '/?error=unauthorized');
      }

      // Create session
      const sessionData = {
        email: userData.email,
        name: userData.name,
        image: userData.picture,
      };

      const sessionCookie = Buffer.from(JSON.stringify(sessionData)).toString('base64');

      // Set cookie and redirect
      res.setHeader('Set-Cookie', `deer-session=${sessionCookie}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=2592000`);
      return res.redirect(302, '/');

    } catch (error) {
      console.error('OAuth error:', error);
      return res.redirect(302, '/?error=oauth_failed');
    }
  }

  if (action === 'signout') {
    // Clear session
    res.setHeader('Set-Cookie', 'deer-session=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0');
    return res.status(200).json({ success: true });
  }

  return res.status(404).json({ error: 'Not found' });
}
