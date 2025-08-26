import React, { useState } from "react";
import api from "../api";

export default function GiftButton({ streamId, onGift, disabled = false }) {
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  const handleClick = async () => {
    if (sending || disabled || !streamId) return;
    setSending(true);
    setError("");
    try {
      await api.post("/api/gifts/", { stream: streamId, gift_type: "rose", amount: 1 });
      onGift?.({ gift: "Rose", amount: 1 });
    } catch (e) {
      if (e?.response?.status === 401) {
        setError("Please log in to send gifts.");
      } else if (e?.response?.status === 400) {
        setError("Invalid request. Check stream.");
      } else {
        setError("Failed to send gift.");
      }
    } finally {
      setSending(false);
    }
  };

  return (
    <div>
      <button
        onClick={handleClick}
        disabled={disabled || sending || !streamId}
        className="inline-flex items-center gap-2 rounded-md border border-input bg-background px-4 py-2 text-sm hover:bg-accent hover:text-accent-foreground disabled:opacity-50"
      >
        {sending ? "Sending..." : "Send Gift"}
        <span className="text-pink-600">💝</span>
      </button>
      {!streamId && (
        <div className="text-xs text-muted-foreground mt-2">No live stream selected.</div>
      )}
      {error && <div className="text-xs text-destructive mt-2">{error}</div>}
    </div>
  );
}


