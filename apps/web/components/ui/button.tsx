"use client";

import { Slot } from "@radix-ui/react-slot";
import { forwardRef, type ButtonHTMLAttributes } from "react";
import { tv, type VariantProps } from "tailwind-variants";

const button = tv({
  base: [
    "relative inline-flex items-center justify-center gap-2",
    "font-mono font-medium tracking-tight whitespace-nowrap select-none",
    "transition-colors duration-150",
    "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-acid)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-bg)]",
    "disabled:pointer-events-none disabled:opacity-40",
    "[&_svg]:size-3.5 [&_svg]:shrink-0",
  ],
  variants: {
    variant: {
      primary: [
        "text-[var(--color-bg)] font-semibold",
        "bg-[var(--color-acid)] hover:bg-[var(--color-acid-glow)]",
        "active:translate-y-px",
      ],
      secondary: [
        "text-[var(--color-fg)]",
        "bg-[var(--color-panel)] border border-[var(--color-line-2)]",
        "hover:bg-[var(--color-panel-hi)] hover:border-[var(--color-line-hi)]",
      ],
      ghost: [
        "text-[var(--color-fg-mute)]",
        "hover:text-[var(--color-fg)] hover:bg-[var(--color-panel-hi)]",
      ],
      danger: [
        "text-[var(--color-rose)]",
        "border border-[oklch(70%_0.24_25/0.3)]",
        "hover:bg-[var(--color-rose-soft)]",
      ],
    },
    size: {
      sm: "h-8 px-3 text-[12px] rounded-md",
      md: "h-10 px-4 text-[13px] rounded-md",
      lg: "h-11 px-5 text-[13.5px] rounded-md",
      icon: "h-10 w-10 rounded-md",
    },
  },
  defaultVariants: { variant: "secondary", size: "md" },
});

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof button> {
  asChild?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        ref={ref}
        className={button({ variant, size, className })}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";
