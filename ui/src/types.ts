export type TierStatus = "tentative" | "established" | "confirmed";

export interface MemoryItemSummary {
  id: string;
  text: string;
  category: string;
  status: TierStatus;
  evidence_count: number;
}

export interface MemoryOp {
  op_type: "ADD" | "REINFORCE" | "SUPERSEDE" | "NOOP";
  target_item_id: string | null;
  text: string | null;
  category: string | null;
}

// SSE event union
export type StreamEvent =
  | { type: "ops"; ops: MemoryOp[] }
  | { type: "profile"; items: MemoryItemSummary[] }
  | { type: "chunk"; text: string }
  | { type: "done" }
  | { type: "error"; message: string };

export interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  ops?: MemoryOp[];
  streaming?: boolean;
}
