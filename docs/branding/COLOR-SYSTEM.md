# Color system

| Rol | Valor base | Uso |
| --- | --- | --- |
| Deep Ink | `#123A3A` | Marca, titulares y superficies oscuras |
| Assurance Teal | `#14A39A` | Señal gráfica y datos destacados |
| Action Teal | `#087F79` | Controles sobre fondo claro |
| Signal Coral | `#FF6B57` | Nodos y acentos breves |
| Coral texto | `#A9362E` | Texto cuando se requiere contraste |
| Pale Mint | `#EAF7F6` | Fondos informativos claros |

Las escalas teal 50–900 y tokens semantic/selected/disabled/overlay viven en
`packages/design-system/tokens.css`. Los estados de negocio siguen usando
success, warning, danger e info; no se infiere significado solo por color.

Objetivo: WCAG 2.2 AA para texto y controles. AAA se busca en cuerpo y contenido
crítico cuando no perjudica jerarquía. Toda combinación nueva requiere prueba.
