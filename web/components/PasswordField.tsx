"use client";

import { useState } from "react";

/**
 * Password input with an eye-toggle to reveal the value. Mobile users + people
 * with disabilities have a hard time typing without seeing what they typed; a
 * silent "wrong password" after a 32-char paste is the most common signup
 * abandon path. This costs nothing.
 */
export function PasswordField({
  id,
  value,
  onChange,
  autoComplete,
  required = true,
  minLength = 8,
}: {
  id: string;
  value: string;
  onChange: (v: string) => void;
  autoComplete?: string;
  required?: boolean;
  minLength?: number;
}) {
  const [show, setShow] = useState(false);
  return (
    <div className="relative">
      <input
        id={id}
        type={show ? "text" : "password"}
        required={required}
        autoComplete={autoComplete}
        minLength={minLength}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-2 pr-9 text-sm text-zinc-100 focus:border-zinc-500 outline-none"
      />
      <button
        type="button"
        onClick={() => setShow((s) => !s)}
        className="absolute right-2 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-200 text-xs px-1"
        aria-label={show ? "Hide password" : "Show password"}
        tabIndex={-1}
      >
        {show ? "Hide" : "Show"}
      </button>
    </div>
  );
}
