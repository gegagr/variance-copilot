import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll, beforeEach } from "vitest";
import { setupServer } from "msw/node";

import { handlers, resetStore } from "./msw/handlers";

export const server = setupServer(...handlers);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => resetStore()); // clean store at the start of every test, regardless of prior writes
afterEach(async () => {
  cleanup(); // unmount React trees so a prior test's DOM never bleeds into the next
  // Let any trailing fire-and-forget request from this test land BEFORE we reset, so a late
  // write can't bleed into the next test's fetch window.
  await new Promise((r) => setTimeout(r, 0));
  server.resetHandlers();
  resetStore();
});
afterAll(() => server.close());

// jsdom doesn't implement scrollIntoView.
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}
