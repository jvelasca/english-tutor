# Plantilla de dossier de auditoría (V3.0)

> Plantilla común para los dossieres `docs/audit/A-*.md` … `G-*.md`. Cada
> dossier sigue la misma estructura para que la consolidación
> (`docs/AUDITORIA-V3.md`) sea directa.

## Alcance

- Qué se audita (componente, archivos, rango de niveles).
- Qué NO se audita (para evitar solapamiento entre auditorías).
- Relación con el freeze de `docs/BETA_V3.md` (§4.1–§4.4).

## Método

1. Instrumentos automáticos usados (scripts, tests, `--quality`).
2. Muestreo (nivel, ids, semilla determinista).
3. Criterios de referencia (tabla `docs/audit/CEFR-REFERENCE.md` o umbrales del motor).

## Evidencia

| Nivel | Ítems/muestras | Métrica A | Métrica B | Veredicto | Notas |
|---|---|---|---|---|---|
| A1 | … | … | … | OK/Revisar/Fallar | … |
| A2 | … | … | … | … | … |

## Hallazgos

| # | Severidad | Hallazgo | Evidencia | Recomendación | Estado |
|---|---|---|---|---|---|
| B1 | media | … | c001… | … | abierto/fix/aceptado |

## Veredicto

**Aprobado con matices / No aprobado.** Resumen de 2-3 líneas.

## Regenerar / Verificar

```powershell
# comandos exactos que reproducen las cifras del dossier
```

## Tests que respaldan

- `backend/tests/test_golden_*.py` (qué caso protege qué).
