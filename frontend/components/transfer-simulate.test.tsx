import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { TransferSimulate } from "./transfer-simulate";
import type { TransferStatus } from "../lib/types";

function renderSimulate(status: TransferStatus) {
  const onSimulate = vi.fn();
  render(
    <TransferSimulate status={status} busy={null} onSimulate={onSimulate} />,
  );
  return onSimulate;
}

describe("TransferSimulate", () => {
  it("processing_transfer_shows_simulate_buttons", () => {
    renderSimulate("processing");

    expect(
      screen.getByRole("button", { name: "Simulate completed" }),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: "Simulate failed" })).toBeTruthy();
  });

  it("non_processing_transfer_hides_simulate_buttons", () => {
    for (const status of [
      "pending",
      "completed",
      "failed",
      "cancelled",
    ] as const) {
      const { unmount } = render(
        <TransferSimulate status={status} busy={null} onSimulate={vi.fn()} />,
      );

      expect(
        screen.queryByRole("button", { name: "Simulate completed" }),
      ).toBeNull();
      expect(screen.queryByRole("button", { name: "Simulate failed" })).toBeNull();
      unmount();
    }
  });

  it("clicking_completed_calls_on_simulate", () => {
    const onSimulate = renderSimulate("processing");

    screen.getByRole("button", { name: "Simulate completed" }).click();

    expect(onSimulate).toHaveBeenCalledWith("completed");
  });

  it("clicking_failed_calls_on_simulate", () => {
    const onSimulate = renderSimulate("processing");

    screen.getByRole("button", { name: "Simulate failed" }).click();

    expect(onSimulate).toHaveBeenCalledWith("failed");
  });
});
