/**
 * Identidad de la COMPILACIÓN que está corriendo (V3.75.8).
 *
 * Hasta ahora la única versión visible en la app era la del **backend**, que llega
 * por `GET /api/health` (`components/SystemStatus.tsx`). Eso deja sin respuesta la
 * pregunta que el alumno hace de verdad cuando algo va raro —«¿qué versión tengo
 * instalada?»— precisamente cuando el backend **no** contesta, o contesta otra
 * distinta de la que sirvió el `dist` que hay en disco. La Ayuda es una pantalla
 * **sin red** (no pide nada a la API), así que su versión no puede depender de
 * ella: se lee del `package.json` en **tiempo de compilación** y viaja dentro del
 * bundle.
 *
 * Consistencia: `scripts/check_release_consistency.py` exige que este número
 * coincida con `backend/config.py::VERSION` y con el resto de orígenes, así que la
 * versión de la compilación y la que declara el backend no pueden divergir en una
 * release publicada. Lo que esta constante **no** dice es *cuándo* se compiló: el
 * `dist` no se versiona y dos compilaciones de la misma versión son la misma
 * compilación declarada.
 *
 * Se importa **el campo**, no el objeto entero: Vite convierte el JSON en exports
 * con nombre y el resto del `package.json` (dependencias, scripts) no entra en el
 * bundle.
 */
import { version } from "../../package.json";

/** Versión de la compilación (misma fuente que la release: `package.json`). */
export const APP_VERSION: string = version;
