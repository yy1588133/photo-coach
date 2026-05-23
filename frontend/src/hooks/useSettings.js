import { useState, useCallback } from "react";

const STORAGE_KEY = "photo-coach-settings";

const DEFAULTS = {
  provider: "anthropic",
  apiKey: "",
  baseUrl: "",
  model: "claude-sonnet-4-20250514",
};

export function useSettings() {
  const [settings, setSettings] = useState(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (!stored) return { ...DEFAULTS };
      const parsed = JSON.parse(stored);
      return { ...DEFAULTS, ...parsed };
    } catch {
      return { ...DEFAULTS };
    }
  });

  const updateSettings = useCallback((patch) => {
    setSettings((prev) => {
      const next = { ...prev, ...patch };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  return [settings, updateSettings];
}
