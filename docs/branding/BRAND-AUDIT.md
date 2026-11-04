# Brand audit

Fecha de corte: 3 de noviembre de 2026. Rama: `codex/branding-identity-system`.
Checkpoint previo: `CP-BRAND-00-20261104T015019Z` (fuente, historial y diff
cifrados; descifrado y bundle verificados).

## Estado comprobado

La base es aprovechable: Inter Variable, Lucide, temas claro/oscuro, tokens CSS,
shell responsive, patrón registro/detalle, skeletons y Playwright+axe. La paleta
teal/carbón/coral ya diferencia el producto. No se recomienda reescribirla.

Brechas prioritarias:

- Solo existía `brand-mark.png` (1254 px, 3D, sin fuente vectorial, variantes ni
  procedencia documentada); pierde legibilidad a 26–40 px.
- Nombres inconsistentes: Perfect Match, Perfect Match Cloud, Perfect Match QMS
  y Quality Management Cloud.
- `styles.css` supera mil líneas y usa radios/colores fuera de tokens.
- La navegación aún no se deriva completamente de rol + capacidad + unidad +
  responsabilidad; ocultar opciones no sustituye autorización del servidor.
- Coral histórico `#DB4B3F` no sirve como texto normal sobre blanco (4.13:1).
- Faltan QA por persona, lector de pantalla, zoom 200/400 %, 320 px y forced colors.

## Decisión

Conservar el sistema funcional y evolucionarlo bajo el territorio **Aligned
Evidence**. No se cambian backend, permisos, modelos, contratos ni autenticación.
Storybook se difiere hasta estabilizar 8–10 primitives reutilizables.

## Herramientas evaluadas

No se instalaron Forge-Space/branding-mcp (archivado), LangChain design-agent
(Alpha y plataforma excesiva), Open-AI-Design-Agent (servicio Muapi y riesgo
SSRF), LogoLoom (rutas de archivo sin allowlist) ni agentic-design-system (sin
licencia). La producción de SVG y tokens se mantiene determinista en el repo.
