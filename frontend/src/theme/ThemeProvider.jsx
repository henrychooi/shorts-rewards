import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { ThemeProvider as MUIThemeProvider, createTheme, CssBaseline } from "@mui/material";

const ThemeModeContext = createContext({ mode: "light", toggle: () => {} });

export function useThemeMode() {
  return useContext(ThemeModeContext);
}

export default function AppThemeProvider({ children }) {
  const [mode, setMode] = useState("light");

  useEffect(() => {
    const saved = localStorage.getItem("mui-theme");
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const initial = saved || (prefersDark ? "dark" : "light");
    setMode(initial);
    document.documentElement.classList.toggle("dark", initial === "dark");
  }, []);

  const toggle = () => {
    const next = mode === "light" ? "dark" : "light";
    setMode(next);
    localStorage.setItem("mui-theme", next);
    document.documentElement.classList.toggle("dark", next === "dark");
  };

  const theme = useMemo(() =>
    createTheme({
      palette: {
        mode,
        primary: { main: mode === "light" ? "#3b82f6" : "#60a5fa" },
        secondary: { main: mode === "light" ? "#10b981" : "#34d399" },
      },
      shape: { borderRadius: 12 },
    }), [mode]
  );

  return (
    <ThemeModeContext.Provider value={{ mode, toggle }}>
      <MUIThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </MUIThemeProvider>
    </ThemeModeContext.Provider>
  );
}


