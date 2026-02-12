"use client";

import React from "react";
import { cn } from "@/lib/utils";

interface ShinyButtonProps {
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
  disabled?: boolean;
  type?: "button" | "submit" | "reset";
}

export function ShinyButton({
  children,
  className,
  onClick,
  disabled,
  type = "button",
}: ShinyButtonProps) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "shiny-button relative cursor-pointer rounded-xl border-2 border-accent-magenta px-8 py-3 font-semibold backdrop-blur-xl transition-all duration-300 ease-in-out hover:scale-110 active:scale-95",
        "bg-gradient-to-b from-accent-magenta/20 via-transparent to-accent-purple/10",
        "hover:border-accent-cyan hover:from-accent-cyan/20 hover:to-accent-magenta/10",
        className
      )}
    >
      <span className="shiny-text relative block size-full tracking-wider text-foreground uppercase">
        {children}
      </span>
      <span className="shiny-overlay absolute inset-0 z-10 block rounded-[inherit] p-px" />
    </button>
  );
}
