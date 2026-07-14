import { describe, expect, it } from "vitest";
import { parseThreadCommand } from "@/lib/threadCommands";

// H2-06 — the single parser both thread pages now share. These lock the exact
// branch behaviour the desktop + mobile `handleNoteOrReport` copies had.

describe("parseThreadCommand — #assign", () => {
  it("parses `#assign @name reason` into assignee + trailing rest", () => {
    const cmd = parseThreadCommand("#assign @jane reassigning to you");
    expect(cmd.kind).toBe("assign");
    expect(cmd.args).toEqual({ assignee: "jane" });
    expect(cmd.rest).toBe("reassigning to you");
  });

  it("parses an email-style mention with no trailing text", () => {
    const cmd = parseThreadCommand("#assign @jane.doe@grm.local");
    expect(cmd).toEqual({ kind: "assign", args: { assignee: "jane.doe@grm.local" }, rest: "" });
  });

  it("tolerates surrounding whitespace (input is trimmed)", () => {
    const cmd = parseThreadCommand("   #assign @bob   ");
    expect(cmd.kind).toBe("assign");
    expect(cmd.args).toEqual({ assignee: "bob" });
  });

  it("treats `#assign` with no mention as a plain note (malformed)", () => {
    const cmd = parseThreadCommand("#assign");
    expect(cmd.kind).toBe("note");
    expect(cmd.rest).toBe("#assign");
  });

  it("treats `#assign @` with an empty mention as a plain note (malformed)", () => {
    expect(parseThreadCommand("#assign @").kind).toBe("note");
  });

  it("does not fire on `#assignfoo` (needs the space + @mention)", () => {
    expect(parseThreadCommand("#assignfoo").kind).toBe("note");
  });
});

describe("parseThreadCommand — #inspect", () => {
  it("parses bare `#inspect` as a self-assigned inspection (assignee null)", () => {
    expect(parseThreadCommand("#inspect")).toEqual({
      kind: "inspect", args: { assignee: null }, rest: "",
    });
  });

  it("parses `#inspect @me` as self (assignee null)", () => {
    expect(parseThreadCommand("#inspect @me").args).toEqual({ assignee: null });
  });

  it("parses `#inspect @officer1` as that assignee", () => {
    const cmd = parseThreadCommand("#inspect @officer1");
    expect(cmd.kind).toBe("inspect");
    expect(cmd.args).toEqual({ assignee: "officer1" });
  });

  it("is case-insensitive on the command token", () => {
    expect(parseThreadCommand("#INSPECT @Me").kind).toBe("inspect");
  });

  it("treats `#inspect look into this` as a NOTE — the command must be the whole line", () => {
    // parseInspectAssignCommand is `$`-anchored; trailing free text disqualifies it.
    const cmd = parseThreadCommand("#inspect look into this");
    expect(cmd.kind).toBe("note");
    expect(cmd.rest).toBe("#inspect look into this");
  });
});

describe("parseThreadCommand — plain notes & ordering", () => {
  it("returns a note for ordinary text", () => {
    expect(parseThreadCommand("please review the dust complaint")).toEqual({
      kind: "note", args: {}, rest: "please review the dust complaint",
    });
  });

  it("returns a note (empty rest) for an empty string", () => {
    expect(parseThreadCommand("")).toEqual({ kind: "note", args: {}, rest: "" });
  });

  it("is pure — identical result on repeat calls (clear-order regression guard)", () => {
    // The desktop/mobile drift was WHERE the match ran relative to clearing the
    // input. As a pure function the parse depends only on its argument, so the hook
    // can safely compute it BEFORE clearing the compose box (the desktop order).
    const input = "#assign @kiran please take this over";
    expect(parseThreadCommand(input)).toEqual(parseThreadCommand(input));
  });
});
