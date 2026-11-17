# ORION JARVIS — isolated Render staging

This is a minimal no-secrets web-service shell for the Render Free plan. It is **not** the full v0.8.0 FastAPI engine, and it cannot chat, read memories, or execute tasks. The original reviewed source is stored in the user's JARVIS v0.8.0 ZIP and should be deployed only after staging security, authentic Supabase sessions, and cost controls are reviewed.

Render plan: Free. Region: Virginia. Branch: orion-jarvis-staging. Auto-deploy: disabled. Nothing is merged into main, and the Orion PIO service remains on its original branch.

Health check: `GET /health`. No OpenAI calls and no privileged database access.

**Warning**: Render Free hours are shared across the workspace; usage beyond included outbound bandwidth/build minutes can be billed when a payment method exists. Verify billing/spend limits before using this service beyond the low-traffic staging probe.
