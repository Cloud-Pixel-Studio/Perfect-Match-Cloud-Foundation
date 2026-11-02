import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, test } from "vitest";
import { ProcessWorkspace } from "../components/process-workspace";

test("process mutations remain hidden until authoritative scope permissions load", () => {
  const markup = renderToStaticMarkup(createElement(ProcessWorkspace));
  expect(markup).toContain("Loading process access");
  expect(markup).not.toContain("New process");
  expect(markup).not.toContain("Save process");
  expect(markup).not.toContain("Archive process");
});
