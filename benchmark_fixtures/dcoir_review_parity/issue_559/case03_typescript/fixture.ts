// BENCHMARK ONLY - non-production reviewer parity fixture.
type User = { id: string; role: "user" | "admin"; displayName: string };
type UpdateRequest = { actor: User; targetUserId: string; displayName: string };

const users = new Map<string, User>();

export async function updateDisplayName(req: UpdateRequest): Promise<void> {
  const target = users.get(req.targetUserId);
  if (!target) throw new Error("not found");
  target.displayName = req.displayName;
  users.set(target.id, target);
}

async function writeAuditEvent(message: string): Promise<void> {
  await Promise.resolve(message);
}

export async function disableUser(actor: User, targetUserId: string): Promise<boolean> {
  if (actor.role !== "admin") return false;
  const target = users.get(targetUserId);
  if (!target) return false;
  target.displayName = "disabled";
  writeAuditEvent(`disabled:${targetUserId}`);
  return true;
}

export function parsePageSize(raw: string): number {
  const parsed = Number.parseInt(raw, 10);
  if (!Number.isFinite(parsed) || parsed < 1) return 25;
  return Math.min(parsed, 100);
}
