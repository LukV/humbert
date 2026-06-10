import { useState } from "react";
import { apiSend } from "../utils/api";
import { t } from "../locales";

interface FeedbackControlsProps {
  cellId: string;
}

type Rating = "up" | "down" | null;

export default function FeedbackControls({ cellId }: FeedbackControlsProps) {
  const [rating, setRating] = useState<Rating>(null);

  const send = async (next: "up" | "down") => {
    setRating(next);
    try {
      await apiSend("/api/feedback", "POST", { cell_id: cellId, rating: next });
    } catch {
      /* silent — JSONL is the truth, not the UI */
    }
  };

  return (
    <div className="feedback-controls">
      <button
        className={`feedback-btn ${rating === "up" ? "feedback-btn--active" : ""}`}
        onClick={() => send("up")}
        aria-label={t("cell.feedback.helpful")}
        title={t("cell.feedback.helpful")}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <path d="M7.493 18.75c-.425 0-.82-.236-.975-.632A7.48 7.48 0 0 1 6 15.375c0-1.75.599-3.358 1.602-4.634.151-.192.373-.309.6-.397.473-.183.89-.514 1.212-.924a9.042 9.042 0 0 1 2.861-2.4c.723-.384 1.35-.956 1.653-1.715a4.498 4.498 0 0 0 .322-1.672V3a.75.75 0 0 1 .75-.75 2.25 2.25 0 0 1 2.25 2.25c0 1.152-.26 2.243-.723 3.218-.266.558.107 1.282.725 1.282h3.126c1.026 0 1.945.694 2.054 1.715.045.422.068.85.068 1.285a11.95 11.95 0 0 1-2.649 7.521c-.388.482-.987.729-1.605.729H14.23c-.483 0-.964-.078-1.423-.23l-3.114-1.04a4.501 4.501 0 0 0-1.423-.23h-.777ZM2.331 10.977a11.969 11.969 0 0 0-.831 4.398 12 12 0 0 0 .52 3.507c.26.85 1.084 1.368 1.973 1.368H4.9c.445 0 .72-.498.523-.898a8.963 8.963 0 0 1-.924-3.977c0-1.708.476-3.305 1.302-4.666.245-.403-.028-.959-.5-.959H4.25c-.832 0-1.612.453-1.918 1.227Z" />
        </svg>
      </button>
      <button
        className={`feedback-btn ${rating === "down" ? "feedback-btn--active" : ""}`}
        onClick={() => send("down")}
        aria-label={t("cell.feedback.not_helpful")}
        title={t("cell.feedback.not_helpful")}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <path d="M15.73 5.25h1.035A7.465 7.465 0 0 1 18 9.375a7.465 7.465 0 0 1-1.235 4.125h-.148c-.806 0-1.534.446-2.031 1.08a9.04 9.04 0 0 1-2.861 2.4c-.723.384-1.35.956-1.653 1.715a4.498 4.498 0 0 0-.322 1.672V21a.75.75 0 0 1-.75.75 2.25 2.25 0 0 1-2.25-2.25c0-1.152.26-2.243.723-3.218.266-.558-.107-1.282-.725-1.282H3.622c-1.026 0-1.945-.694-2.054-1.715A12.137 12.137 0 0 1 1.5 12c0-2.848.992-5.464 2.649-7.521C4.537 3.997 5.136 3.75 5.754 3.75h4.017c.484 0 .968.078 1.43.23l3.105 1.035a6.75 6.75 0 0 0 2.134.345 1.5 1.5 0 0 1 0 3l-.745.001Z" />
          <path d="M21.669 13.773c.536-1.362.831-2.845.831-4.398 0-1.22-.182-2.398-.52-3.507-.26-.85-1.084-1.368-1.973-1.368H19.1c-.445 0-.72.498-.523.898.591 1.2.924 2.55.924 3.977a8.959 8.959 0 0 1-1.302 4.666c-.245.403.028.959.5.959h1.053c.832 0 1.612-.453 1.918-1.227Z" />
        </svg>
      </button>
    </div>
  );
}
