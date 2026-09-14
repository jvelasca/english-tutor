# Auditoría EXTERNA de V3.62.0 — punto de entrada (listo para lanzar)

> **Qué es este archivo.** El prompt **autocontenido** para que un auditor externo
> (que **solo ve el repositorio público** de GitHub) audite la etiqueta
> **`v3.62.0`** antes de autorizar trabajo posterior. La revisión es **de solo
> lectura**: no se cambia código, datos, configuración ni etiquetas publicadas.
>
> **Estado:** entregado 2026-09-14. **Informe esperado:**
> `docs/audit/V-AUDITORIA-TOTAL-V362.md` (letra `V`). La letra `R` sigue
> **reservada** para el informe pendiente de V3.59, que nunca se publicó.

## Objetivo

Auditar profundamente la etiqueta `v3.62.0` (`Student Skill State 4.0: modalidad ×
competencia`) antes de autorizar trabajo posterior.

## Alcance y enfoque

1. Resolver el tag anotado y revisar el diff exacto `v3.61.0..v3.62.0`, la nota de
   release y los commits de documentación posteriores, dejando claro que no existe
   una GitHub Release asociada si esa condición se mantiene.
2. Revisar la taxonomía nueva (`skill_axis`) y el agregador (`skill_state`) contra
   los contratos reales de las cuatro fuentes de evidencia: léxico, Academy,
   listening y pronunciación. Comprobar mapeos ambiguos, inputs legacy, umbrales,
   orden/determinismo y que no invente competencias ni éxito.
3. Revisar la persistencia completa: migración idempotente de `skill_state`,
   compatibilidad con perfiles existentes, serialización JSON, aislamiento por
   usuario, escrituras concurrentes y preservación de columnas ajenas.
4. Seguir el estado hasta `/api/profile` y sus tipos frontend, verificando que sea
   contrato aditivo y que la ausencia de cambio de UI no cree una regresión
   funcional o de representación.
5. Verificar por separado la frontera declarada: el estado v3.62 no debe alterar
   aún el planner, ELV, dificultad, cola léxica ni Context Engine.
6. Ejecutar las pruebas específicas y la suite de backend/lint de la etiqueta en un
   worktree temporal aislado; añadir reproducciones mínimas para hallazgos que
   requieran demostrar un escenario real.
7. Entregar únicamente hallazgos de alta confianza, priorizados por severidad, con
   archivo/línea, escenario, impacto y corrección recomendada; documentar también
   las garantías verificadas y las limitaciones explícitamente diferidas.

## Punto de entrada

- Repositorio: `jvelasca/english-tutor` (público).
- Tag anotado **`v3.62.0`** → commit `f4bcee2`
  (`f4bcee22fbda4a9d280f2582a289994378e33ad2`); commit documental posterior
  `cdd0d97`.
- Base: tag `v3.61.0` → commit `1b4af42`.
- Delta auditado: `1b4af42..f4bcee2` (**19 ficheros, +2642 / −25**, 3 commits).
- Run de CI declarado: **6/6** en
  [34839206611](https://github.com/jvelasca/english-tutor/actions/runs/34839206611)
  (debe estar 6/6; si la API no devuelve runs, declararlo como **documental**).

## Consideraciones

- La nota de v3.62 declara que el nuevo estado todavía no influye en la decisión de
  tareas; se auditará como **contrato intencional**, no como defecto por sí mismo.
- La auditoría tratará como **regresión** cualquier acreditación errónea, mezcla de
  usuarios, reinterpretación de evidencia histórica, pérdida de datos o divergencia
  entre el vector servido y el registrado.
- Los defectos pendientes de v3.60 (filtrado del target en instancias de
  transferencia e identidad inmutable de la superficie) se comprobarán únicamente
  para confirmar que no reaparecen o quedan afectados por este diff; su solución no
  forma parte del alcance declarado de v3.62.

## Afirmaciones a falsar

1. `skill_state` es `{modalidad: {competencia: entry}}` y contiene **todas** las
   modalidades canónicas.
2. Se alimenta de las **cuatro** fuentes (`learning_evidence`, `academy_evidence`,
   `listening_attempts`, `pronunciation_attempts`) y una actividad no se agrega con
   otra en una misma fila canónica.
3. `canonical_competence` **no** usa fuzzy matching y devuelve `""` cuando la
   evidencia no declara la competencia.
4. El aplanado `MODALITY_OF` **nunca** resuelve una competencia; las cadenas
   ambiguas se resuelven por modalidad.
5. La puerta espaciada es la de V3.54 (2 éxitos en 2 días naturales distintos) y el
   gate es el **reutilizado** de `services/competence.py`, sin umbrales nuevos.
6. La evidencia léxica produce entradas de modalidad con `dimensions` y sin
   competencia, con **paridad exacta** con `observed_skill_capacity`.
7. La columna `learning_profile.skill_state` es aditiva, idempotente, con default
   `''`, y las filas legacy quedan con `''`.
8. El contrato `/api/profile` es **aditivo**: ninguna clave de V3.61 se altera.
9. El camino de decisión es **byte-idéntico** con y sin el estado nuevo.
10. Ningún módulo del camino de decisión (`planner`, `difficulty`, `transfer`,
    `lexicon`, `learner_state`, `domain/vocabulary`) menciona el estado nuevo.
11. Los números de verificación declarados (pytest, launcher, vitest, build,
    release consistency, beta gate, content validation, transfer validation).

## Preguntas de alto valor

1. ¿Puede un vocabulario nuevo colarse sin romper la suite de totalidad?
2. ¿Puede una sola actividad acreditar varias competencias y contarse como varias
   ocasiones independientes?
3. ¿Puede una fila de `academy_evidence` sin objetivo resoluble acreditar éxito?
4. ¿Puede el estado mezclar usuarios o servir una caché de otro perfil?
5. ¿Puede la ausencia de invalidación de caché servir un estado obsoleto como
   fresco?
6. ¿Es la `confidence` estadística o de evaluación, y se distingue?
7. ¿Es la dificultad de V3.55 declarada o empíricamente observada?
8. ¿Puede el estado nuevo cambiar la selección de tareas por cualquier vía
   indirecta?
9. ¿Puede reinterpretarse evidencia histórica al añadir la columna?
10. ¿Qué pasa con `interaction`/`mediation` sin competencias y con `receptive` sin
    emisor?

## Formato del informe

Sigue la plantilla de `docs/audit/TEMPLATE.md` más el patrón adoptado por las
auditorías `S`/`T` de V3.60: `Alcance` · `Método` · `Evidencia` · `Hallazgos`
(`| # | Severidad | Hallazgo | Evidencia | Recomendación | Estado |`) ·
`Veredicto` · `Regenerar / Verificar`. Hallazgos `P0`/`P1`/`P2`/`P3` con
`archivo:línea` y severidad `alta`/`media`/`baja`/`documental`.
