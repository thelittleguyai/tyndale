// Tyndale Record API shapes (D5, Phase C — DL-91). Mirrors runtime/app/schemas/record.py.

export interface DeadlineInfo {
  label: string;
  due_date: string | null;
  source: string;
}

export interface ThreeNumberBrief {
  provider_billed: number;
  eob_member_responsibility: number;
  tyndale_computed: number;
}

export interface SubCaseRow {
  case_file_id: string;
  service_date: string | null;
  provider: string | null;
  status: string;
  label: string;
  resume: 'summary' | 'thread';
  three_number: ThreeNumberBrief | null; // null → the row shows needs-documents, not {0,0,0}
  open_item_count: number;
  next_deadline: DeadlineInfo | null;
  recovered_so_far: number; // CONFIRMED only
}

export interface RecordAggregates {
  total_billed_reviewed: number;
  total_recovered: number; // CONFIRMED outcomes only, "so far"
  total_identified: number; // audit ESTIMATE — labeled separately, never recovered
  open_items: number;
  next_check_in_date: string | null;
}

export interface RecordPayload {
  window_months: number;
  sub_cases: SubCaseRow[];
  aggregates: RecordAggregates;
  has_older: boolean;
}
