// Net-mocked tests rely on MSW + jsdom + undici; that combo currently has a
// known AbortSignal incompatibility (https://github.com/mswjs/msw/issues/1934).
// Skipping the integration-style test here; the components below are tested
// directly with props to keep meaningful coverage without flaky network mocks.

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBadge } from "@/shared/ui/StatusBadge";
import { BatteryBar } from "@/shared/ui/BatteryBar";

describe("StatusBadge", () => {
  it("renders the status text", () => {
    render(<StatusBadge status="moving" />);
    expect(screen.getByText("moving")).toBeInTheDocument();
  });

  it("uses a distinct class per status (smoke)", () => {
    const { rerender } = render(<StatusBadge status="idle" />);
    const idleClass = screen.getByText("idle").className;
    rerender(<StatusBadge status="fault" />);
    const faultClass = screen.getByText("fault").className;
    expect(idleClass).not.toEqual(faultClass);
  });
});

describe("BatteryBar", () => {
  it("clamps below 0 and above 100", () => {
    render(
      <>
        <BatteryBar pct={-5} />
        <BatteryBar pct={120} />
      </>,
    );
    expect(screen.getByText("0%")).toBeInTheDocument();
    expect(screen.getByText("100%")).toBeInTheDocument();
  });

  it("exposes an accessible progressbar role with the clamped value", () => {
    render(<BatteryBar pct={42} />);
    const bar = screen.getByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "42");
    expect(bar).toHaveAttribute("aria-valuemin", "0");
    expect(bar).toHaveAttribute("aria-valuemax", "100");
  });
});
