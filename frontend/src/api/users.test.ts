import { afterEach, describe, expect, it, vi } from "vitest";
import { updateUser } from "./users";

describe("users api", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("updateUser propaga el detalle del backend en caso de error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        json: async () => ({ detail: "Campo demasiado largo" }),
      }),
    );
    // `editUser` re-lanza este error (ya no lo traga), de modo que el diálogo
    // de perfil puede mostrar la causa real en lugar del mensaje genérico.
    await expect(
      updateUser("u1", { name: "Nuevo nombre" }),
    ).rejects.toThrow("Campo demasiado largo");
  });

  it("updateUser devuelve el usuario actualizado", async () => {
    const user = { id: "u1", name: "Renombrado", created_at: "x" };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: async () => user }),
    );
    await expect(
      updateUser("u1", { name: "Renombrado" }),
    ).resolves.toEqual(user);
  });
});
