import { useId } from "react";
import type { HunterResidency } from "./residency";

const OPTIONS: { value: HunterResidency; label: string }[] = [
  { value: "", label: "Any" },
  { value: "resident", label: "Resident" },
  { value: "nonresident", label: "Nonresident" },
];

type Props = {
  value: HunterResidency;
  onChange: (value: HunterResidency) => void;
  /** Extra class on the outer fieldset wrapper. */
  className?: string;
  /** Label styling: sidebar uses uppercase muted caption; FilterPanel uses plain text. */
  labelClassName?: string;
  /** Layout of the radio row. */
  layout?: "stack" | "inline";
};

export default function HunterResidencyRadios({
  value,
  onChange,
  className = "",
  labelClassName = "mb-1 block text-xs font-semibold uppercase tracking-wide text-muted",
  layout = "stack",
}: Props) {
  const groupName = useId();
  return (
    <fieldset className={className}>
      <legend className={labelClassName}>Hunter</legend>
      <div
        className={
          layout === "inline"
            ? "mt-1 flex flex-wrap items-center gap-x-3 gap-y-1"
            : "mt-1 flex flex-col gap-1"
        }
        role="radiogroup"
        aria-label="Hunter residency"
      >
        {OPTIONS.map((option) => (
          <label key={option.value || "any"} className="inline-flex items-center gap-1.5 text-sm">
            <input
              type="radio"
              name={groupName}
              value={option.value}
              checked={value === option.value}
              onChange={() => onChange(option.value)}
            />
            <span>{option.label}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
