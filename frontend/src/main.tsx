import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles/fonts.css";
import "./styles/tokens.css";
import "./styles/app.css";
import { FxProvider } from "./fx/FxProvider";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <FxProvider>
      <App />
    </FxProvider>
  </React.StrictMode>
);
