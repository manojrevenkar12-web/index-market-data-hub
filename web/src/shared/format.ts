const level = new Intl.NumberFormat("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const price = new Intl.NumberFormat("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 4 });
const pct = new Intl.NumberFormat("en-GB", { style: "percent", minimumFractionDigits: 2, maximumFractionDigits: 2, signDisplay: "exceptZero" });
const weight = new Intl.NumberFormat("en-GB", { style: "percent", minimumFractionDigits: 1, maximumFractionDigits: 1 });
const day = new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "short", year: "numeric" });
const time = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit" });

export const fmt = {
  level: (x: number) => level.format(x),
  price: (x: number | null) => (x == null ? "none" : price.format(x)),
  change: (x: number) => pct.format(x),
  weight: (x: number) => weight.format(x),
  day: (iso: string) => day.format(new Date(`${iso}T12:00:00`)),
  time: (iso: string) => time.format(new Date(iso)),
};

export const VENDORS = [
  { id: "northwind", letter: "N", name: "Northwind" },
  { id: "meridian", letter: "M", name: "Meridian" },
  { id: "kestrel", letter: "K", name: "Kestrel" },
] as const;
