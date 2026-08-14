import { openDB, DBSchema } from "idb";

const TTL_MS = 48 * 60 * 60 * 1000; // 2 days
const DB_NAME = "skillgap-temp-store";
const STORE_NAME = "sessions";

interface TempRecord {
  key: string;
  value: unknown;
  expiresAt: number;
}

interface SkillGapDB extends DBSchema {
  [STORE_NAME]: {
    key: string;
    value: TempRecord;
  };
}

async function getDb() {
  return openDB<SkillGapDB>(DB_NAME, 1, {
    upgrade(db) {
      db.createObjectStore(STORE_NAME, { keyPath: "key" });
    },
  });
}

export async function saveTemp(key: string, value: unknown) {
  const db = await getDb();
  await db.put(STORE_NAME, { key, value, expiresAt: Date.now() + TTL_MS });
}

export async function getTemp<T>(key: string): Promise<T | null> {
  const db = await getDb();
  const record = await db.get(STORE_NAME, key);
  if (!record) return null;
  if (Date.now() > record.expiresAt) {
    await db.delete(STORE_NAME, key);
    return null;
  }
  return record.value as T;
}

/** Call once on app load: purges any entries past their 48h TTL. */
export async function sweepExpired() {
  const db = await getDb();
  const all = await db.getAll(STORE_NAME);
  const now = Date.now();
  await Promise.all(
    all.filter((r) => now > r.expiresAt).map((r) => db.delete(STORE_NAME, r.key))
  );
}
