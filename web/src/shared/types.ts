export type BoardIndex = {
  id: string;
  name: string;
  currency: string;
  return_type: "price" | "total";
  weighting: "cap" | "equal";
  constituents: number;
  level: number;
  change: number;
  version: number;
  published_at: string;
  corrected_at: string | null;
  first_level: number;
  spark: number[];
};

export type Board = {
  date: string | null;
  days: string[];
  indices: BoardIndex[];
  desk?: { looked_up: number; open: number };
};

export type CandidateQuote = { vendor: string; value: number; repaired: string | null };

export type ConstituentRow = {
  instrument: string;
  isin: string;
  ticker: string;
  mic: string;
  currency: string;
  price: number | null;
  method: "consensus" | "single" | "closest" | "carried" | "desk" | "primary" | "backup" | "median";
  sources: string[];
  reasons: string[];
  candidates: CandidateQuote[];
  version: number;
  weight: number;
};

export type Constituents = { date: string | null; rows: ConstituentRow[] };

export type DeskItem = {
  instrument: string;
  ticker: string;
  topic: "price" | "action";
  reason: string;
  priority: number;
  provisional: number | null;
  looked_up: boolean;
  answer: number | null;
  date: string;
};

export type Desk = { date: string | null; items: DeskItem[] };

export type DesignScore = {
  index_days: number;
  wrong_index_closes: number;
  wrong_after_restatement: number;
  max_index_error_bps: number;
  wrong_prices: number;
  wrong_actions: number;
  desk_lookups: number;
};

export type Report = { world: { business_days: number; seed: number }; designs: Record<string, DesignScore> };
export type Results = { dev?: Report; heldout?: Report };
