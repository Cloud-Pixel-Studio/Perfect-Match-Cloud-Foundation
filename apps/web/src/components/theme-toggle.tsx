"use client";

import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

export function ThemeToggle() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      const stored = window.localStorage.getItem("pm-theme");
      const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      const nextDark = stored ? stored === "dark" : prefersDark;
      setDark(nextDark);
      document.documentElement.dataset.theme = nextDark ? "dark" : "light";
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  function updateTheme(enabled: boolean) {
    setDark(enabled);
    const theme = enabled ? "dark" : "light";
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("pm-theme", theme);
  }

  return (
    <label className="theme-switch">
      <Sun aria-hidden="true" size={16} />
      <span className="sr-only">Use dark theme</span>
      <input
        aria-label="Use dark theme"
        checked={dark}
        onChange={(event) => updateTheme(event.target.checked)}
        type="checkbox"
      />
      <span className="switch-track" aria-hidden="true">
        <span className="switch-thumb" />
      </span>
      <Moon aria-hidden="true" size={16} />
    </label>
  );
}
