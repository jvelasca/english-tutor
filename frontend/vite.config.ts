import { fileURLToPath, URL } from "node:url";
import { hostname } from "node:os";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import basicSsl from "@vitejs/plugin-basic-ssl";

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    // HTTPS con certificado autofirmado: sin él, el acceso desde el móvil por
    // `http://IP` no es un "secure context" y `navigator.mediaDevices` es
    // `undefined`, rompiendo `getUserMedia`. Tras aceptar el aviso de certificado,
    // `https://IP:5173` sí permite la grabación. Se añade el hostname local para
    // que `https://<PC-NAME>:5173` coincida con el SAN del certificado.
    basicSsl({
      name: "english-tutor",
      domains: [hostname(), "english-tutor.local"],
    }),
  ],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: 5173,
    // Escucha en todas las interfaces para que la app sea accesible desde
    // cualquier equipo de la red local (por defecto Vite solo escucha localhost).
    host: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
