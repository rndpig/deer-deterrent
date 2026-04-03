"""
Authentication module for the Deer Deterrent API.

Two auth mechanisms:
1. Firebase ID Token (frontend users) — validated via Firebase Admin SDK
2. Internal API Key (coordinator, ml-detector) — validated against INTERNAL_API_KEY env var
"""
import os
import logging
from typing import Optional

from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

# Lazy-loaded Firebase Admin app
_firebase_app = None
_firebase_init_attempted = False

INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")
FIREBASE_PROJECT_ID = "deer-deterrent-rnp"

# Security scheme for OpenAPI docs
_bearer_scheme = HTTPBearer(auto_error=False)


def _get_firebase_app():
    """Initialize Firebase Admin SDK (once)."""
    global _firebase_app, _firebase_init_attempted
    if _firebase_init_attempted:
        return _firebase_app
    _firebase_init_attempted = True
    try:
        import firebase_admin
        from firebase_admin import credentials
        # Use Application Default Credentials or explicit service account
        cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            _firebase_app = firebase_admin.initialize_app(cred)
            logger.info("Firebase Admin SDK initialized with service account")
        else:
            # Initialize without credentials — can still verify ID tokens
            # if the project ID is set (uses Google's public keys)
            _firebase_app = firebase_admin.initialize_app(options={
                "projectId": FIREBASE_PROJECT_ID,
            })
            logger.info("Firebase Admin SDK initialized with project ID only")
    except Exception as e:
        logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
        _firebase_app = None
    return _firebase_app


def _verify_firebase_token(token: str) -> Optional[dict]:
    """Verify a Firebase ID token. Returns decoded token or None."""
    app = _get_firebase_app()
    if not app:
        logger.warning("Firebase Admin SDK not available — cannot verify token")
        return None
    try:
        from firebase_admin import auth as firebase_auth
        decoded = firebase_auth.verify_id_token(token, app=app)
        return decoded
    except firebase_admin.exceptions.FirebaseError as e:
        logger.debug(f"Firebase token verification failed: {e}")
        return None
    except Exception as e:
        logger.debug(f"Token verification error: {e}")
        return None


def _verify_api_key(key: str) -> bool:
    """Verify an internal API key."""
    if not INTERNAL_API_KEY:
        logger.warning("INTERNAL_API_KEY not configured — rejecting API key auth")
        return False
    # Constant-time comparison to prevent timing attacks
    import hmac
    return hmac.compare_digest(key, INTERNAL_API_KEY)


async def require_auth(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
):
    """Dependency that requires either a valid Firebase token or internal API key.
    
    Accepts:
    - Authorization: Bearer <firebase_id_token>
    - X-API-Key: <internal_api_key>
    
    Sets request.state.user_id and request.state.auth_type on success.
    """
    # Check X-API-Key header first (service-to-service)
    api_key = request.headers.get("X-API-Key")
    if api_key:
        if _verify_api_key(api_key):
            request.state.user_id = "service"
            request.state.auth_type = "api_key"
            return
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Check Bearer token (Firebase)
    if credentials and credentials.credentials:
        decoded = _verify_firebase_token(credentials.credentials)
        if decoded:
            request.state.user_id = decoded.get("uid", "unknown")
            request.state.auth_type = "firebase"
            return
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    raise HTTPException(status_code=401, detail="Authentication required")


async def require_service_auth(request: Request):
    """Dependency that requires internal API key only (service-to-service calls)."""
    api_key = request.headers.get("X-API-Key")
    if api_key and _verify_api_key(api_key):
        request.state.user_id = "service"
        request.state.auth_type = "api_key"
        return
    
    # Also accept Firebase token (admin operations from frontend)
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        decoded = _verify_firebase_token(token)
        if decoded:
            request.state.user_id = decoded.get("uid", "unknown")
            request.state.auth_type = "firebase"
            return

    raise HTTPException(status_code=401, detail="Authentication required")
