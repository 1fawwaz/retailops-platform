// docs/DESIGN-SPEC.md §4: "Currency is £. Never render a currency symbol
// the dataset doesn't use." This is a UK dataset (Online Retail II) end
// to end -- one formatter, used everywhere a money value renders.
const currencyFormatter = new Intl.NumberFormat("en-GB", {
  style: "currency",
  currency: "GBP",
  maximumFractionDigits: 0,
});

export function formatCurrency(value: number): string {
  return currencyFormatter.format(value);
}

const integerFormatter = new Intl.NumberFormat("en-GB");

export function formatInteger(value: number): string {
  return integerFormatter.format(value);
}

// docs/DESIGN-SPEC.md §1: "numbers that align perfectly in a column, at
// every zoom level." A fixed minimumFractionDigits (not just maximum)
// keeps every percentage the same width -- "+10.0%" next to "+14.4%",
// never "+10%" next to "+14.4%".
const percentFormatter = new Intl.NumberFormat("en-GB", {
  style: "percent",
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
  signDisplay: "always",
});

export function formatPercentChange(current: number, previous: number): string | null {
  if (previous === 0) return null;
  return percentFormatter.format((current - previous) / previous);
}
