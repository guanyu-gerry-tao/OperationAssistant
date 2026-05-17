import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";


// Mount React once into the Vite root element provided by frontend/index.html.
createRoot(document.getElementById("root") as HTMLElement).render(
  <StrictMode>
    <App />
  </StrictMode>
);
