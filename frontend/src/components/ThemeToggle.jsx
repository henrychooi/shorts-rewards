import React from "react";
import { useTheme } from "../contexts/ThemeContext";
import "./ThemeToggle.css";

const ThemeToggle = () => {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === "dark";

  return (
    <button
      className={`theme-toggle ${isDark ? "is-dark" : "is-light"}`}
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      aria-pressed={isDark}
      title={isDark ? "Switch to light mode" : "Switch to dark mode"}
      onClick={toggleTheme}
    >
      <span className="toggle-icon sun" aria-hidden>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
          <path d="M6.76 4.84l-1.8-1.79L3.17 4.84l1.79 1.79 1.8-1.79zM1 13h3v-2H1v2zm10 10h2v-3h-2v3zm7.03-18.16l1.79-1.79-1.79-1.79-1.79 1.79 1.79 1.79zM20 13h3v-2h-3v2zM6.76 19.16l-1.8 1.79 1.41 1.41 1.79-1.79-1.4-1.41zM17.24 19.16l1.79 1.79 1.41-1.41-1.8-1.79-1.4 1.41zM12 6a6 6 0 100 12 6 6 0 000-12z" />
        </svg>
      </span>
      <span className="toggle-icon moon" aria-hidden>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12.76 3c-1.07 0-2.11.2-3.07.57C12 5.07 14 8.27 14 12s-2 6.93-4.31 8.43c.96.37 2 .57 3.07.57 5.52 0 10-4.48 10-10S18.28 3 12.76 3z" />
        </svg>
      </span>
      <span className="toggle-knob" />
    </button>
  );
};

export default ThemeToggle;
