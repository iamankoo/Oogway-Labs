import type { LucideIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface NavItemProps {
  icon: LucideIcon;
  label: string;
  badge?: string;
  disabled?: boolean;
  active?: boolean;
  onClick?: () => void;
}

export function NavItem({ icon: Icon, label, badge, disabled, active, onClick }: NavItemProps) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex w-full items-center gap-2 rounded-md px-2 py-2 text-sm transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        active ? "bg-primary-muted text-primary" : "text-foreground hover:bg-accent",
        disabled && "cursor-not-allowed text-muted hover:bg-transparent",
      )}
    >
      <Icon className="size-4 shrink-0" aria-hidden="true" />
      <span className="flex-1 text-left">{label}</span>
      {badge && (
        <Badge variant="outline" className="px-1.5 py-0 text-[10px]">
          {badge}
        </Badge>
      )}
    </button>
  );
}
