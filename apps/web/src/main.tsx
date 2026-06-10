import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

// Self-hosted typefaces (offline-first): Source Serif 4 for narrative, DM Sans
// for UI, JetBrains Mono for code. styles.css references these family names.
import "@fontsource/source-serif-4/300.css";
import "@fontsource/source-serif-4/400.css";
import "@fontsource/source-serif-4/600.css";
import "@fontsource/dm-sans/300.css";
import "@fontsource/dm-sans/400.css";
import "@fontsource/dm-sans/500.css";
import "@fontsource/dm-sans/600.css";
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/500.css";

import "./styles.css";
import App from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
