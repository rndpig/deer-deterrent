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

  const { code } = req.query;
  
  if (!code) {
    return res.redirect(302, '/?error=no_code');
  }

  try {
    // Exchange code for tokens
    const protocol = req.headers['x-forwarded-proto'] || 'https';
    const host = req.headers['x-forwarded-host'] || req.headers.host;
    const redirectUri = `${protocol}://${host}/api/auth/callback`;
    
    const tokenResponse = await fetch('https://oauth2.googleapis.com/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        code,
        client_id: process.env.GOOGLE_CLIENT_ID,
        client_secret: process.env.GOOGLE_CLIENT_SECRET,
        redirect_uri: redirectUri,
        grant_type: 'authorization_code',
      }),
    });

    const tokens = await tokenResponse.json();

    if (!tokens.access_token) {
      console.error('Token response:', tokens);
      return res.redirect(302, '/?error=no_token');
    }

    // Get user info
    const userResponse = await fetch('https://www.googleapis.com/oauth2/v2/userinfo', {
      headers: { Authorization: `Bearer ${tokens.access_token}` },
    });

    const userData = await userResponse.json();

    // Check if user is authorized
    if (userData.email !== allowedEmail) {
      console.log('Unauthorized email:', userData.email);
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
