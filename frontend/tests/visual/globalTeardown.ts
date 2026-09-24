import fs from "node:fs";

import { TESTER_FILE } from "./globalSetup";

/**
 * Cierra el arnés visual borrando el fichero de handshake.
 *
 * Hasta V3.82 aquí se borraba además el perfil `is_test` por API
 * (`DELETE /api/users/{id}`), porque `globalSetup` lo había creado. Ya no hay
 * perfil que borrar —la identidad de los specs es mockeada y la alta pública está
 * cerrada (ver `globalSetup.ts`)—, así que el teardown se queda con lo único que
 * sigue haciendo falta: no dejar el handshake en el árbol de trabajo.
 */
export default async function globalTeardown(): Promise<void> {
  fs.rmSync(TESTER_FILE, { force: true });
}
