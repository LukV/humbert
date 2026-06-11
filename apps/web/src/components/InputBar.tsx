import { useState } from "react";
import { t } from "../locales";

interface InputBarProps {
  variant: "hero" | "compact";
  onAsk: (question: string) => void;
  disabled: boolean;
  hasFollowupContext?: boolean;
}

const CLASSES = {
  hero: { wrapper: "hero-input-wrapper", input: "hero-input", button: "btn-ask" },
  compact: { wrapper: "bottom-input-wrapper", input: "bottom-input", button: "btn-ask-sm" },
};

export default function InputBar({
  variant,
  onAsk,
  disabled,
  hasFollowupContext = false,
}: InputBarProps) {
  const [question, setQuestion] = useState("");
  const cls = CLASSES[variant];

  const placeholder = hasFollowupContext
    ? t("input.placeholder.followup")
    : t("input.placeholder");

  const handleSubmit = () => {
    const trimmed = question.trim();
    if (!trimmed || disabled) return;
    onAsk(trimmed);
    setQuestion("");
  };

  return (
    <div className={cls.wrapper}>
      <input
        type="text"
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") handleSubmit();
        }}
        placeholder={placeholder}
        disabled={disabled}
        className={cls.input}
      />
      <button
        onClick={handleSubmit}
        disabled={disabled || !question.trim()}
        className={cls.button}
      >
        {t("input.submit")}
      </button>
    </div>
  );
}
