import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { ErrorBoundary } from "./components/ErrorBoundary";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {/* V3.77.2: sin boundary, un throw durante el render desmonta la app
        entera (React no los atrapa por su cuenta). Este es el radio mayor:
        envuelve todo y no depende del contexto de i18n. */}
    <ErrorBoundary scope="app">
      <App />
    </ErrorBoundary>
  </StrictMode>,
);
