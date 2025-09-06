import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./styles/globals.css";
import { ViewCountProvider } from "./contexts/ViewCountContext";
import { LikeCountProvider } from "./contexts/LikeCountContext";
import { ThemeProvider } from "./contexts/ThemeContext";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <ThemeProvider>
      <ViewCountProvider>
        <LikeCountProvider>
          <App />
        </LikeCountProvider>
      </ViewCountProvider>
    </ThemeProvider>
  </StrictMode>
);
