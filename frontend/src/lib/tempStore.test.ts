import { describe, expect, it, vi } from "vitest";
import { IDBFactory as FakeIDBFactory } from "fake-indexeddb";
import type { saveTemp, getTemp, sweepExpired } from "./tempStore";

const TTL_MS = 48 * 60 * 60 * 1000;

type TempStore = {
  saveTemp: typeof saveTemp;
  getTemp: typeof getTemp;
  sweepExpired: typeof sweepExpired;
};

async function freshStore(): Promise<TempStore> {
  // idb caches IndexedDB connections by database name in a module-level Map.
  // resetModules() re-evaluates idb (fresh connection map) while a new
  // FakeIDBFactory gives a fresh database — together they keep every test
  // isolated and fast (no deleteDatabase races, no hangs).
  vi.resetModules();
  globalThis.indexedDB = new FakeIDBFactory();
  return import("./tempStore");
}

describe("tempStore", () => {
  it("saves and returns a value", async () => {
    const { saveTemp, getTemp } = await freshStore();
    const payload = { match_score: 42 };
    await saveTemp("report-1", payload);
    const result = await getTemp<typeof payload>("report-1");
    expect(result).toEqual(payload);
  });

  it("returns null for a missing key", async () => {
    const { getTemp } = await freshStore();
    expect(await getTemp("nope")).toBeNull();
  });

  it("expires a value whose expiresAt is in the past", async () => {
    const { saveTemp, getTemp } = await freshStore();
    await saveTemp("stale", { a: 1 });

    // Backdate the record directly in IndexedDB to simulate TTL expiry.
    const db = await new Promise<IDBDatabase>((resolve, reject) => {
      const req = indexedDB.open("skillgap-temp-store");
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction("sessions", "readwrite");
      const store = tx.objectStore("sessions");
      store.put({ key: "stale", value: { a: 1 }, expiresAt: Date.now() - 1000 });
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
    db.close();

    // A past expiresAt makes getTemp return null and removes the entry.
    expect(await getTemp("stale")).toBeNull();
    expect(await getTemp("stale")).toBeNull();
  });

  it("sweepExpired removes expired entries and keeps valid ones", async () => {
    const { saveTemp, getTemp, sweepExpired } = await freshStore();
    await saveTemp("valid", { keep: true });
    await saveTemp("expired", { drop: true });

    const db = await new Promise<IDBDatabase>((resolve, reject) => {
      const req = indexedDB.open("skillgap-temp-store");
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction("sessions", "readwrite");
      const store = tx.objectStore("sessions");
      store.put({ key: "expired", value: { drop: true }, expiresAt: Date.now() - 1 });
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
    db.close();

    await sweepExpired();

    expect(await getTemp("valid")).toEqual({ keep: true });
    expect(await getTemp("expired")).toBeNull();
  });

  it("uses a 48h TTL when saving", async () => {
    const { saveTemp } = await freshStore();
    const now = Date.now();
    vi.spyOn(Date, "now").mockReturnValue(now);

    await saveTemp("ttl-check", { t: 1 });

    const db = await new Promise<IDBDatabase>((resolve, reject) => {
      const req = indexedDB.open("skillgap-temp-store");
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
    const record = await new Promise<{ expiresAt: number } | undefined>((resolve, reject) => {
      const tx = db.transaction("sessions", "readonly");
      const req = tx.objectStore("sessions").get("ttl-check");
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
    db.close();
    vi.restoreAllMocks();

    expect(record?.expiresAt).toBe(now + TTL_MS);
  });
});
