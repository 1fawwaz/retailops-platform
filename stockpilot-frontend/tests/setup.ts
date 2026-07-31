import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => {
  cleanup();
});

// jsdom has no ResizeObserver AND reports every element as 0x0 (no real
// layout engine) -- Recharts' ResponsiveContainer (components/charts/*)
// waits for its ResizeObserver callback to report a nonzero size before
// rendering any children at all, so a no-op stub leaves every chart test
// rendering an empty <div> forever. This stub fires once, synchronously,
// with a plausible fixed size, mimicking a real observer's initial
// callback.
class ResizeObserverStub implements ResizeObserver {
  #callback: ResizeObserverCallback;

  constructor(callback: ResizeObserverCallback) {
    this.#callback = callback;
  }

  observe(target: Element) {
    const rect = { width: 600, height: 240 } as DOMRectReadOnly;
    this.#callback(
      [{ target, contentRect: rect } as ResizeObserverEntry],
      this,
    );
  }

  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = ResizeObserverStub;

Object.defineProperty(HTMLElement.prototype, "offsetWidth", {
  configurable: true,
  value: 600,
});
Object.defineProperty(HTMLElement.prototype, "offsetHeight", {
  configurable: true,
  value: 240,
});
HTMLElement.prototype.getBoundingClientRect = function getBoundingClientRect() {
  return {
    width: 600,
    height: 240,
    top: 0,
    left: 0,
    right: 600,
    bottom: 240,
    x: 0,
    y: 0,
    toJSON() {
      return this;
    },
  } as DOMRect;
};
