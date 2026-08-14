import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBadge } from "./status-badge";
import type { TransferStatus } from "../lib/types";

describe("StatusBadge", () => {
  it("status_badge_renders_status_text", () => {
    const cases: Array<[TransferStatus, string]> = [
      ["pending", "Pending"],
      ["processing", "Processing"],
      ["completed", "Completed"],
      ["failed", "Failed"],
      ["cancelled", "Cancelled"],
    ];

    for (const [status, label] of cases) {
      const { unmount } = render(<StatusBadge status={status} />);
      expect(screen.getByText(label)).toBeTruthy();
      unmount();
    }
  });
});