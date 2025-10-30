import "@testing-library/jest-dom";
import "whatwg-fetch";

class ResizeObserver {
  callback;
  constructor(callback) {
    this.callback = callback;
  }
  observe() {}
  unobserve() {}
  disconnect() {}
}

if (typeof window !== "undefined" && !window.ResizeObserver) {
  window.ResizeObserver = ResizeObserver;
}

if (typeof global !== "undefined" && !global.ResizeObserver) {
  global.ResizeObserver = ResizeObserver;
}
