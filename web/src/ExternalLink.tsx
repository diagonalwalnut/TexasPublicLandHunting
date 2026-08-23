import type { ReactNode } from "react";
import { safeExternalUrl } from "./urls";

type Props = {
  href?: string | null;
  className?: string;
  children: ReactNode;
};

export default function ExternalLink({ href, className, children }: Props) {
  const safe = safeExternalUrl(href);
  if (!safe) return null;
  return (
    <a className={className} href={safe} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  );
}
