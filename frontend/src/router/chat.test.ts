import { describe, expect, it } from "vitest";
import {
  chatSkillFromPath,
  chatSkillPath,
  isChatSkill,
  isChatSkillSlug,
  type ChatSkill,
} from "./chat";

describe("chatSkillPath (V3.73.1)", () => {
  it("construye la ruta canónica de cada destreza de chat", () => {
    expect(chatSkillPath("reading")).toBe("/chat/lectura");
    expect(chatSkillPath("writing")).toBe("/chat/escritura");
  });
});

describe("chatSkillFromPath", () => {
  it("reconoce las dos sub-rutas canónicas", () => {
    expect(chatSkillFromPath("/chat/lectura")).toBe("reading");
    expect(chatSkillFromPath("/chat/escritura")).toBe("writing");
  });

  it("tolera hashes, trailing slash y valores percent-encoded", () => {
    expect(chatSkillFromPath("#/chat/lectura")).toBe("reading");
    expect(chatSkillFromPath("/chat/escritura/")).toBe("writing");
  });

  it("devuelve null fuera de la raíz /chat o con una hoja desconocida", () => {
    expect(chatSkillFromPath("/chat")).toBeNull();
    expect(chatSkillFromPath("/chat/otra")).toBeNull();
    expect(chatSkillFromPath("/chat/lectura/extra")).toBeNull();
    expect(chatSkillFromPath("/aprender/lectura")).toBeNull();
    expect(chatSkillFromPath("/")).toBeNull();
  });

  it("hace round-trip con chatSkillPath", () => {
    const skills: ChatSkill[] = ["reading", "writing"];
    for (const skill of skills) {
      expect(chatSkillFromPath(chatSkillPath(skill))).toBe(skill);
    }
  });
});

describe("isChatSkill / isChatSkillSlug", () => {
  it("acepta solo las dos destrezas de chat", () => {
    expect(isChatSkill("reading")).toBe(true);
    expect(isChatSkill("writing")).toBe(true);
    expect(isChatSkill("speaking")).toBe(false);
    expect(isChatSkill("grammar")).toBe(false);
    expect(isChatSkill(null)).toBe(false);
  });

  it("isChatSkillSlug reconoce solo los slugs canónicos", () => {
    expect(isChatSkillSlug("lectura")).toBe(true);
    expect(isChatSkillSlug("escritura")).toBe(true);
    expect(isChatSkillSlug("reading")).toBe(false);
    expect(isChatSkillSlug("otra")).toBe(false);
    expect(isChatSkillSlug(undefined)).toBe(false);
  });
});
