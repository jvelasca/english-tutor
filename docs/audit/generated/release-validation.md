# Validación automática de la release (V3.73)

Versión del árbol: `3.75.2` · **10 pass · 0 fail · 0 skip**

Generado por `scripts/validation_gate.py auto`. No sustituye a los gates
humanos: solo cubre lo que se puede comprobar estáticamente.

| # | Comprobación | Estado | Detalle |
|---|---|---|---|
| 1 | La versión es consistente en todos los orígenes | ✅ pass | OK: Release consistency (3.75.2) en todos los orígenes |
| 2 | i18n sin claves huérfanas ni sin definir | ✅ pass |   -> docs/audit/generated/i18n-report.{json,md} |
| 3 | El producto no arranca sin la UI compilada | ✅ pass | fail-closed cableado en launcher y backend |
| 4 | El descubrimiento de la LAN no usa direcciones públicas | ✅ pass | net_interfaces.py enumera el propio equipo |
| 5 | El CI prueba el launcher y el origen de producto en Windows | ✅ pass | 2 jobs en windows-latest |
| 6 | Los protocolos de los gates apuntan al origen de producto | ✅ pass | 3 protocolos en :8000 y sin dev server |
| 7 | Instrumento de red sin deriva | ✅ pass | 9 puntos declarados y vigentes |
| 8 | Los 7 gates están definidos y documentados | ✅ pass | 7 gates declarados |
| 9 | El artefacto de la UI está construido | ✅ pass | index.html servible |
| 10 | La evidencia registrada es válida | ✅ pass | sin evidencia todavía (los 7 gates están en `pending`) |

Los 7 gates de validación física se registran con `validation_gate.py record` (que sella el commit validado) y se consultan con `status --strict`; con los 7 en `pass`, `status --strict --same-tree` exige además que la evidencia sea de este mismo commit.
