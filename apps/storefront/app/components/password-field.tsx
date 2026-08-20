/** A password `<input>` with a show/hide toggle, so a customer can check
 * what they typed before submitting.
 *
 * Uncontrolled by design, like every password field in this app -- forms
 * here read values from `FormData` on submit, not from React state, so this
 * only ever toggles the `type` attribute and forwards everything else
 * (`name`, `required`, `minLength`, ...) untouched. */

import { Eye, EyeOff } from "lucide-react";
import { useState, type InputHTMLAttributes } from "react";

import { useLocalizeText } from "../lib/i18n/localized-text";

export function PasswordField({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  const localize = useLocalizeText();
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <input
        type={visible ? "text" : "password"}
        className={`${className ?? ""} pr-10`}
        {...props}
      />
      <button
        type="button"
        onClick={() => setVisible((value) => !value)}
        className="absolute inset-y-0 right-0 flex items-center px-3 text-ink-muted hover:text-ink"
        aria-label={visible ? localize("Hide password") : localize("Show password")}
      >
        {visible ? <EyeOff size={16} /> : <Eye size={16} />}
      </button>
    </div>
  );
}
