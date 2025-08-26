import React, { useState } from "react";

export default function GiftButton({ onGift, disabled = false }) {
  const [sending, setSending] = useState(false);

  const handleClick = async () => {
    if (sending || disabled) return;
    setSending(true);
    try {
      await new Promise((r) => setTimeout(r, 500));
      onGift?.({ gift: "Rose", amount: 1 });
    } finally {
      setSending(false);
    }
  };

  return (
    <button
      onClick={handleClick}
      disabled={disabled || sending}
      className="inline-flex items-center gap-2 rounded-md border border-input bg-background px-4 py-2 text-sm hover:bg-accent hover:text-accent-foreground disabled:opacity-50"
    >
      {sending ? "Sending..." : "Send Gift"}
      <span className="text-pink-600">💝</span>
    </button>
  );
}


