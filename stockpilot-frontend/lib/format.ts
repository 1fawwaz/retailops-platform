// docs/DESIGN-SPEC.md §4: "Currency is ₹. Never render a currency symbol
// the dataset doesn't use." This is an India dataset end
// to end -- one formatter, used everywhere a money value renders.
const currencyFormatter = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

export function formatCurrency(value: number): string {
  return currencyFormatter.format(value);
}

// formatCurrency's 0-decimal rounding is right for aggregate KPI totals
// (revenue, inventory value) but would silently misrepresent a per-unit
// price -- ₹0.49 rounds to "₹0", which isn't a rounding nicety, it's a
// wrong price. Used for anything that's a real per-line/per-unit money
// value: product sale_price/unit_cost, PO/SO line prices, invoice
// totals, payment amounts.
const preciseCurrencyFormatter = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function formatCurrencyPrecise(value: number): string {
  return preciseCurrencyFormatter.format(value);
}

const integerFormatter = new Intl.NumberFormat("en-IN");

export function formatInteger(value: number): string {
  return integerFormatter.format(value);
}

// docs/DESIGN-SPEC.md §1: "numbers that align perfectly in a column, at
// every zoom level." A fixed minimumFractionDigits (not just maximum)
// keeps every percentage the same width -- "+10.0%" next to "+14.4%",
// never "+10%" next to "+14.4%".
const percentFormatter = new Intl.NumberFormat("en-IN", {
  style: "percent",
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
  signDisplay: "always",
});

export function formatPercent(value: number): string {
  return percentFormatter.format(value);
}

export function formatPercentChange(current: number, previous: number): string | null {
  if (previous === 0) return null;
  return percentFormatter.format((current - previous) / previous);
}
