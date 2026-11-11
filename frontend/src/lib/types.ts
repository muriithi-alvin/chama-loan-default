// Shapes returned by the Python API (src/chama/web/routes).

export type Role = "official" | "member" | "admin";
export type Band = "low" | "medium" | "high";
export type Effect = "raises risk" | "lowers risk";

export interface Me {
  user: {
    name: string;
    role: Role;
    position: string | null;
    chama_id: string;
    chama_name: string;
    member_code: string | null;
  };
}

/** Before sign-in: which ways to sign in are switched on (D-037). */
export interface Site {
  demo_mode: boolean;
  sign_in_ready: boolean;
  methods: { password: boolean; google: boolean; phone: boolean };
  officials_confirm_by_phone: boolean;
}

/** A sign-in waiting for its texted code. */
export interface CodeStep {
  next: "code";
  phone_hint: string;
}

export interface ApiErrorBody {
  error: { code: string; message: string; ref: string; field?: string };
}

export interface Reason {
  feature: string;
  sentence: string;
  effect: Effect;
}

export interface ScoreSource {
  page_no: number;
  meeting_month: string;
  meeting_date: string | null;
  model_run_id: string;
  model_label: string;
  model_version: string | null;
  model_checksum: string | null;
  scored_at: string;
}

export interface Meeting {
  page_no: number;
  meeting_month: string;
  meeting_date: string | null;
}

export interface Overview {
  chama: { id: string; name: string };
  last_meeting: Meeting | null;
  scores: ScoreSource | null;
  scores_behind: boolean;
  counts: { high: number; medium: number; low: number; no_loan: number };
  strand: { code: string; name: string; band: Band; moved_from: Band | null }[];
  follow_up: { code: string; name: string; band: Band; reason: Reason }[];
  health: { open_loans: number; outstanding: number; running_last_meeting: number; missed_last_meeting: number };
  last_scan?: { upload_id: number; page_no: number; accepted_at: string; accepted_by: string } | null;
}

export interface MemberRow {
  code: string;
  name: string;
  band: Band | null;
  open_loans: number;
  outstanding: number;
  missed_last_3: number | null;
}

export interface MemberPage {
  code: string;
  name: string;
  member_since: number | null;
  band: Band | null;
  meaning: string | null;
  note: string;
  reasons: Reason[];
  source: ScoreSource | null;
  loans: {
    type: "normal" | "emergency" | "school_fees";
    issued_month: string | null;
    due_month: string | null;
    status: string;
    running: boolean;
    outstanding: number;
    amount: number | null;
    rolled_into_month: string | null;
  }[];
  repayments: {
    page_no: number;
    meeting_month: string;
    meeting_date: string | null;
    loan_type: string;
    balance_before: number | null;
    repaid: number | null;
    interest: number | null;
    balance_after: number | null;
    missed: boolean;
  }[];
  contributions: { page_no: number; meeting_month: string; amount: number | null; paid: boolean }[];
}

export interface MeetingRow {
  page_no: number;
  meeting_month: string;
  meeting_date: string | null;
  date_estimated: boolean;
  contribution_total: number | null;
  total_collection: number | null;
  lines: number;
  new_loans: number;
  source: PageSource;
  has_issues: boolean;
}

export interface MeetingPage {
  page_no: number;
  meeting_month: string;
  meeting_date: string | null;
  date_estimated: boolean;
  source: PageSource;
  footer: Record<"contribution_total" | "brought_forward" | "total_collection" | "cash" | "banked", number | null>;
  unclear: boolean;
  issues: string | null;
  photo: { available: boolean; reason: string | null };
  lines: {
    line: number;
    name: string;
    code: string | null;
    kind: string;
    loan_type: string | null;
    monthly: number | null;
    monthly_note: string | null;
    balance_before: number | null;
    repaid: number | null;
    interest: number | string | null;
    balance_after: number | null;
    due_month: string | null;
    unclear: boolean;
    issues: string | null;
  }[];
  new_loans: { name: string; code: string | null; amount: number | null; loan_type: string; loan_month: string | null }[];
  previous: number | null;
  next: number | null;
}

/** typed: from the yearly Excel files; scanned: a photo; entered: typed into Kibaba (D-038). */
export type PageSource = "typed" | "scanned" | "entered";

export type UploadStatus = "queued" | "reading" | "ready" | "failed" | "accepted" | "discarded";

export interface Upload {
  id: number;
  status: UploadStatus;
  problem: string | null;
  provider: string | null;
  model: string | null;
  seconds: number | null;
  page_no: number | null;
  meeting_date: string | null;
  source: "photo" | "typed";
  parts: number;
  step?: string | null;
  created_at: string;
  accepted_at: string | null;
  attempts: number;
  run_id: number | null;
  run_status: RunStatus | null;
  uploaded_by?: string;
  edits?: number;
}

export type RunStatus = "queued" | "running" | "done" | "failed";
export type DraftTable = "meetings" | "statements" | "new_loans";

export interface DraftFlag {
  row_id: number;
  col: string | null;
  rule: string;
  level: "check" | "hint";
  message: string;
}

export interface DraftRow {
  id: number;
  table: DraftTable;
  cells: Record<string, string | null>;
  added: boolean;
  flags: DraftFlag[];
}

export interface Draft {
  upload_id: number;
  status: UploadStatus;
  source: "photo" | "typed";
  photo: { available: boolean; reason: string | null; parts: number };
  columns: Record<DraftTable, { key: string; label: string }[]>;
  rows: DraftRow[];
  names: { raw: string; member: string | null; is_new: boolean; known_spelling: boolean; suggestions: { name: string; score: number }[] }[];
  members: string[];
  ready_to_accept: boolean;
  problems: { field: string; message: string }[];
}

export interface Run {
  id: number;
  upload_id: number;
  status: RunStatus;
  page_no: number | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  steps: { step: string; position: number; status: "waiting" | "running" | "done" | "failed"; started_at: string | null; finished_at: string | null; error_message: string | null }[];
  source: "photo" | "typed";
  changed_members: { code: string; name: string; band: Band | null; reason: string | null }[];
}

/** For the Type-a-page form (D-038). */
export interface TypedInfo {
  last_meeting: Meeting | null;
  last_accepted: string | null;
  members: string[];
  loans_carried: number;
  waiting: number;
}

export interface Edit {
  id: number;
  upload_id: number;
  row_id: number | null;
  tbl: string;
  col: string | null;
  action: "edit" | "add_row" | "delete_row" | "match_name";
  old_value: string | null;
  new_value: string | null;
  edited_at: string;
  edited_by_name: string;
  page_no: number | null;
}

export interface RecordsStatus {
  records_to: Meeting | null;
  model_label?: string | null;
  scored_at?: string | null;
}
