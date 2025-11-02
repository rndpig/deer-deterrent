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

  const session = req.cookies?.['deer-session'];

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
