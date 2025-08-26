import React from "react";

export function Avatar({ className = "", children, ...props }) {
  return (
    <div
      className={[
        "relative flex h-10 w-10 shrink-0 overflow-hidden rounded-full",
        className,
      ].join(" ")}
      {...props}
    >
      {children}
    </div>
  );
}

export function AvatarImage({ src, alt = "", className = "", ...props }) {
  return (
    <img
      src={src}
      alt={alt}
      className={["aspect-square h-full w-full", className].join(" ")}
      {...props}
    />
  );
}

export function AvatarFallback({ children, className = "", ...props }) {
  return (
    <div
      className={[
        "flex h-full w-full items-center justify-center rounded-full bg-muted",
        className,
      ].join(" ")}
      {...props}
    >
      <span className="text-sm font-medium text-muted-foreground">{children}</span>
    </div>
  );
}

export default Avatar;


