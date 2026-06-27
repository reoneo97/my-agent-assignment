import type {
  InteractionResponse,
  MockAlarmResponse,
  Operator,
  ShiftEndResponse,
  Synopsis,
} from "./types";

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json();
}

export function sendUserMessage(operatorId: string, message: string, sessionId?: string): Promise<InteractionResponse> {
  return post("/api/interaction", { operator_id: operatorId, session_id: sessionId, source: "user", message });
}

export function sendSimulated(operatorId: string, sessionId?: string): Promise<InteractionResponse> {
  return post("/api/interaction", { operator_id: operatorId, session_id: sessionId, source: "simulated" });
}

export function mockAlarm(operatorId: string): Promise<MockAlarmResponse> {
  return post("/api/alarm/mock", { operator_id: operatorId });
}

export function closeSession(
  operatorId: string,
  outcome: "resolved_independently" | "escalated",
  sessionId?: string,
): Promise<InteractionResponse> {
  return post("/api/interaction", { operator_id: operatorId, session_id: sessionId, source: "user", outcome });
}

export function endShift(operatorId: string, shift = "day"): Promise<ShiftEndResponse> {
  return post("/api/shift/end", { operator_id: operatorId, shift });
}

export function fetchSynopsis(operatorId: string): Promise<Synopsis> {
  return get(`/api/synopsis/${operatorId}`);
}

export function fetchOperators(): Promise<{ operators: Operator[] }> {
  return get("/api/operators");
}

export function resetOperator(operatorId: string): Promise<void> {
  return post(`/api/reset/${operatorId}`);
}

