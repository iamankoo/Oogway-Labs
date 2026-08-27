import { Monitor, Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";

type ThemePreference = "light" | "dark" | "system";

const STORAGE_KEY = "lenny-theme-preference";

function readStoredPreference(): ThemePreference {
  if (typeof window === "undefined") return "system";
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return stored === "light" || stored === "dark" ? stored : "system";
}

const NEXT_PREFERENCE: Record<ThemePreference, ThemePreference> = {
  light: "dark",
  dark: "system",
  system: "light",
};

const PREFERENCE_META: Record<ThemePreference, { icon: typeof Sun; label: string }> = {
  light: { icon: Sun, label: "Light theme" },
  dark: { icon: Moon, label: "Dark theme" },
  system: { icon: Monitor, label: "System theme" },
};

export function ThemeToggle() {
  const [preference, setPreference] = useState<ThemePreference>(readStoredPreference);

  useEffect(() => {
    const root = document.documentElement;
    if (preference === "system") {
      root.removeAttribute("data-theme");
    } else {
      root.setAttribute("data-theme", preference);
    }
    window.localStorage.setItem(STORAGE_KEY, preference);
  }, [preference]);

  const { icon: Icon, label } = PREFERENCE_META[preference];

  return (
    <Button
      variant="ghost"
      size="sm"
      className="w-full justify-start gap-2 text-muted hover:text-foreground"
      onClick={() => setPreference(NEXT_PREFERENCE[preference])}
      aria-label={`Appearance: ${label}. Activate to switch.`}
    >
      <Icon className="size-4" aria-hidden="true" />
      <span>{label}</span>
    </Button>
  );
}
