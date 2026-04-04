"""
Authentication module for the Deer Deterrent API.

Two auth mechanisms:
1. Firebase ID Token (frontend users) — validated via PyJWT + Google's public keys
2. Internal API Key (coordinator, ml-detector) — validated against INTERNAL_API_KEY env var
"""
import os
import logging
import time
from typing import Optional, Dict, Any

import jwt
import requests
from cryptography.x509 import load_pem_x509_certificate
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")
FIREBASE_PROJECT_ID = "deer-deterrent-rnp"

# Google's public certificates for Firebase token verification
GOOGLE_CERTS_URL = "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"

# Cached certificates and expiry time
_cached_certs: Dict[str, Any] = {}
_certs_expiry: float = 0

# Security scheme for OpenAPI docs
_bearer_scheme = HTTPBearer(auto_error=False)


def _get_google_certs() -> Dict[str, Any]:
    """Fetch and cache Google's public certificates for JWT verification."""
    global _cached_certs, _certs_expiry
    
    # Return cached certs if still valid
    if _cached_certs and time.time() < _certs_expiry:
        return _cached_certs
    
    try:
        resp = requests.get(GOOGLE_CERTS_URL, timeout=10)
        resp.raise_for_status()
        
        # Parse cache-control header for expiry
        cache_control = resp.headers.get("Cache-Control", "")
        max_age = 3600  # Default 1 hour
        for part in cache_control.split(","):
            if "max-age=" in part:
                try:
                    max_age = int(part.split("=")[1].strip())
                except ValueError:
                    pass
        
        # Convert PEM certificates to public keys
        certs_json = resp.json()
        _cached_certs = {}
        for kid, cert_pem in certs_json.items():
            cert = load_pem_x509_certificate(cert_pem.encode())
            _cached_certs[kid] = cert.public_key()
        
        _certs_expiry = time.time() + max_age
        logger.info(f"Fetched {len(_cached_certs)} Google certificates, cached for {max_age}s")
        return _cached_certs
    except Exception as e:
        logger.error(f"Failed to fetch Google certificates: {e}")
        return _cached_certs  # Return stale cache if available


def _verify_firebase_token(token: str) -> Optional[dict]:
    """Verify a Firebase ID token using PyJWT + Google's public certificates."""
    try:
        # Get the key ID from token header
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        if not kid:
            logger.warning("Token missing 'kid' in header")
            return None
        
        # Get Google's public keys
        certs = _get_google_certs()
        if kid not in certs:
            # Refresh certs in case of rotation
            global _certs_expiry
            _certs_expiry = 0  # Force refresh
            certs = _get_google_certs()
            if kid not in certs:
                logger.warning(f"Unknown key ID: {kid}")
                return None
        
        public_key = certs[kid]
        
        # Verify the token
        decoded = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=FIREBASE_PROJECT_ID,
            issuer=f"https://securetoken.google.com/{FIREBASE_PROJECT_ID}",
        )
        
        # Additional Firebase-specific validations
        if not decoded.get("sub"):
            logger.warning("Token missing 'sub' claim")
            return None
        if decoded.get("auth_time", 0) > time.time():
            logger.warning("Token auth_time is in the future")
            return None
        
        logger.info(f"Token verified for uid={decoded.get('sub', 'unknown')}")
        return decoded
    except jwt.ExpiredSignatureError:
        logger.warning("Token has expired")
        return None
    except jwt.InvalidAudienceError:
        logger.warning(f"Invalid audience in token")
        return None
    except jwt.InvalidIssuerError:
        logger.warning(f"Invalid issuer in token")
        return None
    except jwt.PyJWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        return None
    except Exception as e:
        logger.warning(f"Token verification error: {type(e).__name__}: {e}")
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
