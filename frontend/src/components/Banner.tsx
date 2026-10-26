import type { ReactNode } from "react";

interface BannerProps {
  tone: "warn" | "error" | "info";
  title: string;
  children?: ReactNode;
}

const ICON = { warn: "⚠", error: "✖", info: "ℹ" } as const;

/** Icon + text, so tone is never conveyed by colour alone. */
export function Banner({ tone, title, children }: BannerProps) {
  return (
    <div className={`banner banner--${tone}`} role={tone === "info" ? "note" : "alert"}>
      <span className="banner__icon" aria-hidden="true">
        {ICON[tone]}
      </span>
      <div>
        <strong>{title}</strong>
        {children}
      </div>
    </div>
  );
}
