# Design tool evaluation

Fecha de corte: 3 de noviembre de 2026.

| Candidato | Resultado | Razón principal |
| --- | --- | --- |
| Forge Space Branding MCP | No integrar | Repositorio archivado y sin mantenimiento activo. |
| LangChain design-agent | No integrar | Estado Alpha y plataforma mayor que la necesidad actual. |
| Open-AI-Design-Agent | Rechazado | Dependencia de servicio externo y superficie SSRF/proxy. |
| LogoLoom | Diferido | MCP útil, pero las rutas arbitrarias requieren hardening/allowlist. |
| agentic-design-system | No integrar | Sin licencia publicada y compatibilidad React no demostrada. |

El stack seleccionado usa SVG determinista, tokens CSS, Inter Variable, Lucide,
Next/React, Playwright y axe ya presentes. Imagegen integrado produjo únicamente
el hero abstracto original. No se añadieron dependencias ni servicios externos,
por lo que el costo operativo incremental del sistema de diseño es cero; el
costo de generación puntual depende del plan de la herramienta y no se registra
como costo recurrente del SaaS.

La evaluación no equivale a una auditoría permanente. Versiones, licencias y
riesgos deben revisarse otra vez antes de reconsiderar cualquiera de los MCP.
