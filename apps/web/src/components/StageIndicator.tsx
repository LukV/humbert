import { t } from "../locales";

interface StageIndicatorProps {
  stage: string;
}

export default function StageIndicator({ stage }: StageIndicatorProps) {
  // t() falls back to the raw key for an unknown stage; show the bare stage then.
  const key = `stage.${stage}`;
  const label = t(key);

  return (
    <div className="stage-indicator">
      <div className="processing-dots">
        <span />
        <span />
        <span />
      </div>
      {label === key ? stage : label}
    </div>
  );
}
