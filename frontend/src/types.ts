export type Lead = {
  id: number;
  revision: number;
  customer_name: string;
  lead_id: string;
  enquiry_date: string;
  contact_no: string;
  email_id: string;
  alt_no: string;
  model: string;
  quantity: number;
  city: string;
  dealer: string;
  voice_of_customer: string;
  category: string;
  remark: string;
  responded: string;
  relevance: string;
  deal_temperature: string;
  outcome: string;
  status: string;
  follow_up_date: string;
  updated_at: string;
  created_at: string;
  remark_preview?: string;
};
export type Activity = {
  id: number;
  kind: string;
  body: string;
  sender: string;
  occurred_at: string;
};
export type History = {
  id: number;
  snapshot: Record<string, string | number | null>;
  changed_fields: string[];
  saved_at: string;
};
export type Reminder = {
  id: number;
  lead_id: number;
  due_at: string;
  note: string;
  completed_at: string;
  customer_name: string;
  contact_no: string;
  status: string;
  call_id: string;
};
export type Detail = {
  lead: Lead;
  activities: Activity[];
  history: History[];
  reminders: Reminder[];
  enquiry_time: string;
  remark_text: string;
};
export type Settings = {
  mailbox_paths: string[];
  sender_filter: string;
  my_email: string;
  database_path?: string;
};
export type Collection = {
  id: number;
  label: string;
  year: number | null;
  from_date: string;
  to_date: string;
  updated_at: string;
  total: number;
};
export type CollectionRequest = {
  collection_id?: number;
  year?: number;
  from_date?: string;
  to_date?: string;
  rescan?: boolean;
};
export type Job = {
  running: boolean;
  finished_at: string;
  collection?: Collection | null;
  error: string;
  result: null | {
    new_leads: number;
    updated_leads: number;
    out_of_range: number;
    remarks_added: number;
    unparsed: number;
    pending: number;
    errors: string[];
    issues: { folder: string; subject: string; reason: string }[];
  };
};
export const fields: Record<string, string> = {
  customer_name: "Customer name",
  lead_id: "Call ID",
  enquiry_date: "Enquiry date",
  contact_no: "Phone",
  email_id: "Email",
  alt_no: "Alternate phone",
  model: "Model",
  quantity: "Quantity",
  city: "City",
  dealer: "Dealer",
  voice_of_customer: "Voice of Customer",
  category: "Category",
  remark: "Remark",
  responded: "Customer Responded or Not",
  relevance: "Relevant / Irrelevant deals",
  deal_temperature: "Hot / Cold / Warm Deals",
  status: "Status",
  follow_up_date: "Next follow-up",
  enquiry_time: "Email date & time",
};
export const statuses = [
  "New",
  "In process",
  "Follow-up",
  "Quotation Sent",
  "Won",
  "Lost",
  "Closed",
];
export const responses = [
  "",
  "Responded",
  "Not Responded",
  "No Answer",
  "Callback",
];
