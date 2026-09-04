import { afterEach, describe, expect, it, vi } from "vitest";
import {
  addSpeakingRouteExtras,
  getSpeakingAudioUrl,
  getSpeakingLevelItems,
  getSpeakingQuestion,
  getSpeakingRouteExtrasJob,
  getSpeakingStats,
  listSpeakingRouteExtras,
  removeSpeakingRouteExtra,
  submitSpeakingAttempt,
} from "./speakingRoutes";

function mockFetch(ok: boolean, data: unknown) {
  const fn = vi.fn().mockResolvedValue({ ok, json: async () => data });
  vi.stubGlobal("fetch", fn);
  return fn;
}

describe("speakingRoutes api", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("getSpeakingQuestion llama con user_id en la query", async () => {
    const fn = mockFetch(true, { id: "s1", level: "A1", phrase: "Hi" });
    await getSpeakingQuestion("u1");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/speaking/question?user_id=u1");
  });

  it("getSpeakingQuestion añade level y mode=failed solo cuando se piden", async () => {
    const fn = mockFetch(true, { id: "s1", level: "A1", phrase: "Hi" });
    await getSpeakingQuestion("u1", "A1", "failed");
    const [url] = fn.mock.calls[0];
    expect(url).toBe(
      "/api/speaking/question?user_id=u1&level=A1&mode=failed",
    );
  });

  it("getSpeakingQuestion con mode all omite el parámetro", async () => {
    const fn = mockFetch(true, { id: "s1", level: "A1", phrase: "Hi" });
    await getSpeakingQuestion("u1", "A1", "all");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/speaking/question?user_id=u1&level=A1");
  });

  it("getSpeakingStats llama con user_id en la query", async () => {
    const fn = mockFetch(true, { attempts: 1, passed: 1, accuracy: 100 });
    await getSpeakingStats("u1");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/speaking/stats?user_id=u1");
  });

  it("getSpeakingLevelItems llama a /items con user_id y level", async () => {
    const fn = mockFetch(true, {
      level: "A1",
      total: 2,
      mastered: 0,
      failed: 1,
      unseen: 1,
      completed: false,
      items: [],
    });
    await getSpeakingLevelItems("u1", "A1");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/speaking/items?user_id=u1&level=A1");
  });

  it("getSpeakingAudioUrl construye la URL del audio con user_id y kind", () => {
    expect(getSpeakingAudioUrl("s1", "u1")).toBe(
      "/api/speaking/audio/s1?user_id=u1&kind=opening",
    );
    expect(getSpeakingAudioUrl("s1", "u1", "model")).toBe(
      "/api/speaking/audio/s1?user_id=u1&kind=model",
    );
  });

  it("submitSpeakingAttempt envía FormData con file y phrase_id al endpoint", async () => {
    const fn = mockFetch(true, {
      phrase_id: "s1",
      level: "A1",
      app_line: "Hi! How are you?",
      heard: "I am fine",
      model_response: "Great, thanks!",
      overall: 0.9,
      passed: true,
      criteria: {},
      observed: {},
    });
    const blob = new Blob(["audio"], { type: "audio/webm" });
    await submitSpeakingAttempt("u1", "s1", blob);
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/speaking/attempt?user_id=u1");
    expect(init.body).toBeInstanceOf(FormData);
    const form = init.body as FormData;
    expect(form.get("phrase_id")).toBe("s1");
    const file = form.get("file");
    expect(file).toBeInstanceOf(File);
    expect((file as File).name).toBe("audio.webm");
    expect((file as Blob).type).toBe("audio/webm");
    expect(await (file as Blob).text()).toBe("audio");
  });

  it("addSpeakingRouteExtras POSTea {count} al nivel", async () => {
    const fn = mockFetch(true, {
      job_id: "j1",
      status: "running",
      level: "A1",
      requested: 10,
      added: [],
      error: "",
    });
    await addSpeakingRouteExtras("u1", "A1", 10);
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/speaking/routes/A1/extras?user_id=u1");
    expect(JSON.parse(init.body as string)).toEqual({ count: 10 });
  });

  it("getSpeakingRouteExtrasJob lee el estado del trabajo", async () => {
    const fn = mockFetch(true, {
      job_id: "j1",
      status: "done",
      level: "A1",
      requested: 10,
      added: ["s2", "s3"],
      error: "",
    });
    await getSpeakingRouteExtrasJob("u1", "A1", "j1");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/speaking/routes/A1/extras/jobs/j1?user_id=u1");
  });

  it("listSpeakingRouteExtras y removeSpeakingRouteExtra usan DELETE", async () => {
    const fnList = mockFetch(true, { level: "A1", total: 1, phrase_ids: ["s2"] });
    await listSpeakingRouteExtras("u1", "A1");
    expect(fnList.mock.calls[0][0]).toBe(
      "/api/speaking/routes/A1/extras?user_id=u1",
    );

    const fnDel = mockFetch(true, { level: "A1", total: 0, phrase_ids: [] });
    await removeSpeakingRouteExtra("u1", "A1", "s2");
    const [url, init] = fnDel.mock.calls[0];
    expect(url).toBe("/api/speaking/routes/A1/extras/s2?user_id=u1");
    expect(init.method).toBe("DELETE");
  });
});
