import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles/app.css";
import { AdminBootstrapGate } from "./components/accounts/AdminBootstrapGate";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <AdminBootstrapGate>
        <App />
      </AdminBootstrapGate>
  </React.StrictMode>
);
