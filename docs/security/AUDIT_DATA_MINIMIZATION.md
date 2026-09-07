# Audit Data Minimization

Audit payloads are built by trusted server code. The service rejects forbidden credential-like keys and payloads larger than 64 KiB, and never accepts a client action name. Passwords, session/CSRF values, authorization codes, PKCE and login bindings, access/refresh/ID tokens, cookies, API/private/client/database/AWS/GitHub credentials are prohibited. The current tenant-selection event records only a safe selection marker and never the previous tenant.
