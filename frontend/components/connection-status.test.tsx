import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ConnectionStatus } from "./connection-status";

describe("ConnectionStatus", () => {
  it("connected_status_shows_live", () => {
    render(<ConnectionStatus status="connected" />);

    expect(screen.getByText("Live")).toBeTruthy();
  });

  it("offline_status_shows_offline", () => {
    render(<ConnectionStatus status="offline" />);

    expect(screen.getByText("Offline")).toBeTruthy();
  });

  it("reconnecting_status_shows_reconnecting", () => {
    render(<ConnectionStatus status="reconnecting" />);

    expect(screen.getByText("Reconnecting…")).toBeTruthy();
  });
});
