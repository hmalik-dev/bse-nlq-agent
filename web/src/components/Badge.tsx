import type { JSX } from "react";
import type { Badge as BadgeName } from "../types";

// Intrinsic sizes of the marks, so the width and height attributes keep the
// real aspect ratio while CSS sets the rendered height.
const MARKS: Record<BadgeName, { src: string; alt: string; width: number; height: number }> = {
  nets: { src: "/brand/nets.svg", alt: "Brooklyn Nets", width: 215, height: 215 },
  liberty: { src: "/brand/liberty.svg", alt: "New York Liberty", width: 200, height: 170 },
};

/** A 24px team mark. Decorative: it always sits beside text that names the team. */
export function Badge({ name }: { name: BadgeName }): JSX.Element {
  const mark = MARKS[name];
  return (
    <img
      src={mark.src}
      alt=""
      title={mark.alt}
      width={mark.width}
      height={mark.height}
      className="block h-6 w-auto shrink-0"
      data-badge={name}
    />
  );
}

/** Which team mark a row or question carries, if any, read from its text. */
export function badgeFor(text: string): BadgeName | null {
  if (/brooklyn nets/i.test(text)) return "nets";
  if (/new york liberty/i.test(text)) return "liberty";
  return null;
}
