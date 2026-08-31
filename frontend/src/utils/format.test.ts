import { describe, expect, it } from "vitest";
import { formatDuration, formatUptime, pct, relativeTime } from "./format";

describe("format helpers", () => {
  it("formats percentages with sensible precision", () => {
    expect(pct(4.23)).toBe("4.2%");
    expect(pct(42)).toBe("42%");
    expect(pct(null)).toBe("—");
  });

  it("formats durations", () => {
    expect(formatDuration(5)).toBe("5s");
    expect(formatDuration(90)).toBe("1m 30s");
    expect(formatDuration(null)).toBe("—");
  });

  it("formats uptime", () => {
    expect(formatUptime(7200)).toBe("2h 0m");
    expect(formatUptime(90000)).toBe("1d 1h");
  });

  it("produces relative time", () => {
    expect(relativeTime(new Date(Date.now() - 5000).toISOString())).toBe("just now");
    expect(relativeTime(new Date(Date.now() - 3_600_000).toISOString())).toContain("ago");
  });
});
