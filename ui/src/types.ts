export type TierStatus = "tentative" | "established" | "confirmed";

export interface ProfileItem {
  id: string;
  text: string;
  category: string;
  status: TierStatus;
  evidence_count: number;
  source_event_ids: string[];
  last_updated: string;
}

export interface Profile {
  operator_id: string;
  items: ProfileItem[];
}

export interface Signal {
  category: string;
  value: string;
  observation: string;
}

export interface MemoryOp {
  op_type: "ADD" | "REINFORCE" | "SUPERSEDE" | "NOOP";
  target_item_id: string | null;
  text: string | null;
  category: string | null;
}

export interface InteractionSummary {
  id: string;
  operator_message: string;
  timestamp: string;
  alarm_code: string | null;
  shift: string | null;
}

export interface InteractionResponse {
  interaction: InteractionSummary;
  assistant_reply: string;
  signals_extracted: Signal[];
  memory_operations: MemoryOp[];
  profile: Profile;
}

export interface TierTransition {
  item_id: string;
  from_status: string;
  to_status: string;
}

export interface ShiftChanges {
  tier_transitions: TierTransition[];
  new_items: ProfileItem[];
  superseded: { item_id: string; by: string }[];
}

export interface ShiftEndResponse {
  no_significant_updates: boolean;
  changes: ShiftChanges;
  profile_before: Profile;
  profile_after: Profile;
  synopsis_before: string;
  synopsis_after: string;
}

export interface Synopsis {
  text: string;
  generated_at: string;
  version: number;
}

export interface Operator {
  id: string;
  name: string;
  machine_type: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  text: string;
  signals?: Signal[];
  ops?: MemoryOp[];
  loading?: boolean;
}

export interface Alarm {
  code: string | null;
  machine_id: string | null;
  complexity: string | null;
  severity: string | null;
  expected_disposition: string | null;
}

export interface MockAlarmResponse {
  session_id: string;
  alarm: Alarm;
  system_message: string;
  proactive_reply: string | null;
}
