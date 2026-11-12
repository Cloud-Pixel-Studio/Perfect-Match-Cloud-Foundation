import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, test } from "vitest";

import { QMSAccessWorkspace } from "../components/qms-access-workspace";

test("grant controls stay hidden until scoped access data loads", () => {
  const owner = renderToStaticMarkup(createElement(QMSAccessWorkspace, { role: "owner", userId: "self" }));
  expect(owner).toContain("Loading QMS permissions");
  expect(owner).not.toContain('aria-label="Grant QMS access"');
  for (const role of ["admin", "member", "auditor"]) {
    const readOnly = renderToStaticMarkup(createElement(QMSAccessWorkspace, { role, userId: "self" }));
    expect(readOnly).toContain("My QMS permissions");
    expect(readOnly).not.toContain('aria-label="Grant QMS access"');
    expect(readOnly).not.toContain("Confirm revoke");
  }
});
