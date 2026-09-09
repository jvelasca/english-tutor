# Candidato V3.32 — Dictionary → Learning Bridge (borrador de diseño, sin implementar)

> Rol: documento de diseño para el siguiente incremento. **No es una orden de
> implementación**: las sesiones de 2026-09-09 cerraron V3.30.1 (endurecimiento
> de la auditoría V3.30.0) y V3.31 (robustez del diccionario y contrato, ver
> `release-notes-v3.31.0.md`); este borrador se redactó originalmente para
> V3.31 y queda aquí como esquema del candidato **V3.32**. Antes de
> implementarlo, revisar `docs/RELEVO.md` (nota superior), `PLAN.md` («Estado
> actual» y «Siguiente incremento») y el dossier
> `docs/DISENO-V330-DICCIONARIO-CONSULTA.md` (decisiones D1/D2/D3 de V3.30 que
> este candidato debe respetar).
> Fecha del borrador: 2026-09-09 · Release objetivo: v3.32.0.

## Objetivo

Convertir el diccionario de consulta (V3.30) en la **puerta natural de entrada
al aprendizaje adaptativo**, sin romper la decisión D3: «consultar» sigue
siendo solo lectura y **nunca** genera evidencia; «practicar» (una acción
explícita del alumno sobre una palabra consultada) crea una actividad real cuyo
éxito SÍ puede alimentar el Student Model.

                 DICTIONARY
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
    Definition    Context      Usage
        │            │            │
        └────────────┼────────────┘
                     ▼
                PRACTICE
                     │
          ┌──────────┼──────────┐
          ▼          ▼          ▼
     Recognition   Recall   Production
          │          │          │
          └──────────┼──────────┘
                     ▼
                  Transfer
                     │
                     ▼
                 Retention
                     │
                     ▼
              Student Model

## Invariante fundamental (heredada de D3)

- **Consultar ≠ aprender.** Un lookup no crea filas en `vocabulary`, no registra
  eventos ni mueve mastery (ya blindado por tests en V3.30 y V3.30.1).
- **Practicar ≠ consultar.** El botón «Practicar» en la tarjeta del diccionario
  abre una actividad real; solo el resultado de ESA actividad (y no el mero
  lookup) puede escribir en el Student Model a través de los puntos de volcado
  existentes (`record_production`, `record_exposure`, retrievals, FSRS…).

## Arquitectura propuesta

1. **Semilla mínima (primer eslabón, reutilizable).** Añadir una acción
   «Practicar esta palabra» a la entrada del diccionario que reutilice el
   micro-drill existente (palabra/frase del hub Vocabulario, V3.19–V3.21):
   Recognition (MCQ sobre la definición) → Recall → Production (drill oral /
   sentence). El volcado de producción sigue usando los canales/actividades
   actuales (`as_unit=True`, `activity="drill"`), de modo que la evidencia es
   idéntica a la de cualquier otra práctica y NO distingue su origen.
2. **Sin etiquetas de origen en el Student Model.** No se persiste «vino del
   diccionario» como campo de evidencia (evitaría contaminar la semántica de
   canal/actividad); si hiciera falta telemetría de producto, usar un evento de
   `learning_events` informativo sin peso de mastery.
3. **Escaleras por destreza (después del primer eslabón).** Reconocimiento
   (MCQ definición ↔ palabra), recall demorado (reutilizar el scheduler FSRS),
   producción en contexto y transferencia por contexto de actividad (V3.23).
4. **Frontend.** La tarjeta de `DictionaryLookup` crece; si el candidato añade
   varios bloques, dividir el componente (DictionarySearch / DictionaryEntryCard /
   DictionaryDefinition / DictionaryExample / DictionaryUsage /
   DictionaryUnitUsage) **antes** de acumular más secciones.

## Deuda estructural declarada (fuera de V3.32)

- Polisemia por senses (una entrada ≠ inventario de sentidos; relevante en B2+).
- Definición adaptada al CEFR del alumno (hoy el prompt pide «simple English»
  sin `learner_level`).
- Diccionario contexto-aware (headword + sentence + nivel) para transcriptos de
  listening con palabras tocables.
- Rate limit local de generación y caché negativa con TTL (P2 de la auditoría
  V3.30.0, no urgentes en LAN).

## Criterios de aceptación (cuando se implemente)

- Test e2e: lookup no crea evidencia; lookup + «Practicar» + éxito de práctica
  SÍ crea la misma evidencia que esa práctica fuera del diccionario.
- Test de aislamiento entre usuarios del contenido y de la práctica.
- Sin regresiones en V3.30/V3.30.1 (single-flight, `generator_version`,
  `UNUSABLE_MODELS`).
