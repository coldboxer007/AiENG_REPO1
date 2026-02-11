# Security Implementation Guide

This document describes the security measures implemented in the Financial Data MCP Server.

## Overview

The MCP server implements comprehensive security measures following OWASP recommendations:

1. **HTTP Security Headers** - Prevent XSS, clickjacking, and other attacks
2. **CORS Configuration** - Control cross-origin access
3. **Request ID Tracking** - Enable request tracing and debugging
4. **Rate Limiting** - Prevent abuse and DoS attacks

## Security Headers

All HTTP responses include the following security headers:

### Strict-Transport-Security (HSTS)
```http
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
```

**Purpose:** Forces HTTPS connections and prevents SSL stripping attacks.

**Values:**
- `max-age=31536000` - Cache for 1 year
- `includeSubDomains` - Apply to all subdomains
- `preload` - Allow browser preload lists

### X-Content-Type-Options
```http
X-Content-Type-Options: nosniff
```

**Purpose:** Prevents MIME type sniffing which can lead to XSS attacks.

### X-Frame-Options
```http
X-Frame-Options: DENY
```

**Purpose:** Prevents clickjacking attacks by disallowing iframes.

**Options:**
- `DENY` - Never allow framing (most secure)
- `SAMEORIGIN` - Allow from same origin only
- `ALLOW-FROM uri` - Allow from specific URI

### Content-Security-Policy (CSP)
```http
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline' https://unpkg.com https://cdn.redoc.ly; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://unpkg.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'
```

**Purpose:** Mitigates XSS attacks by controlling resource loading.

**Directives:**
- `default-src 'self'` - Default to same origin
- `script-src` - Allow scripts from self, inline, and CDNs (for Swagger UI)
- `style-src` - Allow styles from self, inline, and fonts
- `font-src` - Allow fonts from self and Google
- `img-src` - Allow images from self, data URIs, and HTTPS
- `connect-src 'self'` - Allow API calls to self only
- `frame-ancestors 'none'` - Prevent framing (redundant with X-Frame-Options)
- `base-uri 'self'` - Restrict base tag
- `form-action 'self'` - Restrict form submissions

### Referrer-Policy
```http
Referrer-Policy: strict-origin-when-cross-origin
```

**Purpose:** Controls referrer information sharing to protect privacy.

**Behavior:**
- Same origin: Full URL sent
- Cross-origin: Only origin sent
- Downgrade (HTTPS→HTTP): No referrer sent

### Permissions-Policy
```http
Permissions-Policy: accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()
```

**Purpose:** Disables browser features and APIs that aren't needed.

### X-Request-ID
```http
X-Request-ID: 550e8400-e29b-41d4-a716-446655440000
```

**Purpose:** Unique identifier for request tracing across logs and services.

**Characteristics:**
- Generated for every request
- UUID v4 format
- Used for debugging and audit trails

## CORS Configuration

Cross-Origin Resource Sharing (CORS) is configured via environment variables:

```bash
# Allow all origins (development only)
ALLOWED_ORIGINS=*

# Allow specific origins (production)
ALLOWED_ORIGINS=https://app1.com,https://app2.com
```

### CORS Headers

When enabled, responses include:
```http
Access-Control-Allow-Origin: https://app.example.com
Access-Control-Allow-Credentials: true
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS
Access-Control-Allow-Headers: *
```

### Preflight Requests

The server handles OPTIONS preflight requests automatically:
```
OPTIONS /tools/search_companies
Origin: https://app.example.com
Access-Control-Request-Method: POST

HTTP/1.1 200 OK
Access-Control-Allow-Origin: https://app.example.com
Access-Control-Allow-Methods: POST
Access-Control-Max-Age: 600
```

## Security Configuration

### Environment Variables

```bash
# Enable/disable security headers (default: true)
ENABLE_SECURITY_HEADERS=true

# Allowed CORS origins (default: * for development)
ALLOWED_ORIGINS=https://app.example.com,https://admin.example.com

# Enable RLS for database (default: false)
ENABLE_RLS=true

# Admin API key for bypassing RLS
ADMIN_API_KEY=your-secret-admin-key
```

### Production Checklist

Before deploying to production:

- [ ] Change `ALLOWED_ORIGINS` from `*` to specific domains
- [ ] Set strong `ADMIN_API_KEY`
- [ ] Enable `ENABLE_RLS` for multi-tenant deployments
- [ ] Configure TLS/SSL certificates
- [ ] Set up rate limiting (already enabled by default)
- [ ] Review CSP policies for your specific needs
- [ ] Enable request logging for audit trails

## Security Testing

### Test Security Headers

```bash
# Check all security headers
curl -I http://localhost:8000/health

# Verify HSTS
curl -I http://localhost:8000/health | grep -i strict-transport

# Verify CSP
curl -I http://localhost:8000/health | grep -i content-security

# Verify CORS
curl -H "Origin: http://localhost:3000" \
     -I http://localhost:8000/health | grep -i access-control
```

### Test CORS Preflight

```bash
curl -X OPTIONS http://localhost:8000/tools/search_companies \
     -H "Origin: http://localhost:3000" \
     -H "Access-Control-Request-Method: POST" \
     -H "Access-Control-Request-Headers: Content-Type" \
     -v
```

### Test Request ID

```bash
# Each request should have unique X-Request-ID
curl -I http://localhost:8000/health | grep -i x-request-id
```

## Security Headers in Python

### Using the Middleware

```python
from fastapi import FastAPI
from app.middleware.security import SecurityHeadersMiddleware

app = FastAPI()
app.add_middleware(SecurityHeadersMiddleware)
```

### Customizing Headers

```python
from app.middleware.security import SecurityHeadersMiddleware

class CustomSecurityMiddleware(SecurityHeadersMiddleware):
    def _add_content_security_policy(self, response):
        # Custom CSP for your application
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' https://trusted-cdn.com;"
        )

app.add_middleware(CustomSecurityMiddleware)
```

### Disabling Headers for Specific Routes

```python
@app.get("/public-info")
async def public_info(response: Response):
    # Remove specific headers for this route
    response.headers.pop("X-Frame-Options", None)
    return {"message": "Public information"}
```

## OWASP Compliance

This implementation follows OWASP Secure Headers Project recommendations:

| Header | OWASP Recommended | Our Implementation | Status |
|--------|-------------------|-------------------|---------|
| Strict-Transport-Security | Required | max-age=31536000 | ✅ |
| X-Content-Type-Options | Required | nosniff | ✅ |
| X-Frame-Options | Required | DENY | ✅ |
| Content-Security-Policy | Required | Strict policy | ✅ |
| Referrer-Policy | Recommended | strict-origin-when-cross-origin | ✅ |
| Permissions-Policy | Recommended | Restrictive | ✅ |
| X-Request-ID | Best Practice | UUID v4 | ✅ |

## Security Scanning

### Using securityheaders.com

Test your deployment:
```
https://securityheaders.com/?q=https://your-api.com&followRedirects=on
```

Expected grade: **A+**

### Using Mozilla Observatory

```
https://observatory.mozilla.org/analyze/your-api.com
```

Expected score: **100/100**

### Using curl

```bash
# Score your headers
curl -s -D- http://localhost:8000/health -o /dev/null | grep -E "^HTTP|^[A-Z]"
```

## Troubleshooting

### Issue: CORS Errors in Browser

**Symptoms:** Browser shows CORS errors when calling API

**Solutions:**
1. Check `ALLOWED_ORIGINS` includes your domain
2. Ensure preflight OPTIONS requests are handled
3. Verify `Access-Control-Allow-Credentials` if using cookies/auth

### Issue: CSP Blocking Resources

**Symptoms:** Swagger UI or ReDoc not loading properly

**Solutions:**
1. Check browser console for CSP violations
2. Add required domains to `script-src` or `style-src`
3. Use `unsafe-inline` only if absolutely necessary

### Issue: Security Headers Not Present

**Symptoms:** `curl -I` shows no security headers

**Solutions:**
1. Check `ENABLE_SECURITY_HEADERS=true` in config
2. Verify middleware is added to FastAPI app
3. Check middleware order (security should be early)

### Issue: HSTS Causing Issues in Development

**Symptoms:** Browser forces HTTPS on localhost

**Solutions:**
1. Clear browser HSTS cache (chrome://net-internals/#hsts)
2. Set `ENABLE_SECURITY_HEADERS=false` in development
3. Use incognito/private browsing mode

## References

- [OWASP Secure Headers Project](https://owasp.org/www-project-secure-headers/)
- [MDN Web Security](https://developer.mozilla.org/en-US/docs/Web/Security)
- [Content Security Policy](https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP)
- [CORS Guide](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)
- [Helmet.js Security Headers](https://helmetjs.github.io/)

## Security Contact

For security issues or questions:
- Review this documentation
- Check the [OWASP Cheat Sheet](https://cheatsheetseries.owasp.org/)
- Report vulnerabilities responsibly
