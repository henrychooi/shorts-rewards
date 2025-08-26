import React from "react";

const baseClasses = "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 h-10 px-4 py-2";

const variants = {
  default: "bg-primary text-primary-foreground hover:bg-primary/90",
  outline: "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
  ghost: "hover:bg-accent hover:text-accent-foreground",
};

const sizes = {
  sm: "h-9 px-3",
  lg: "h-11 px-8 text-base",
};

export function Button({
  className = "",
  variant = "default",
  size,
  children,
  ...props
}) {
  const variantClasses = variants[variant] || variants.default;
  const sizeClasses = size ? sizes[size] || "" : "";
  const classes = [baseClasses, variantClasses, sizeClasses, className]
    .filter(Boolean)
    .join(" ");
  return (
    <button className={classes} {...props}>
      {children}
    </button>
  );
}

export default Button;


