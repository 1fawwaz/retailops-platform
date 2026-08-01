// docs/CLAUDE.md §7: "Pagination, sorting, and filtering params follow
// the one convention defined in lib/api/list-params.ts -- don't let a
// resource invent its own query-param shape." Every StockPilot Core
// list endpoint that supports search/pagination uses these same names
// (search, limit, offset) -- see contracts/stockpilot-api/versions/v1.json
// for /inventory/stock, /products, /suppliers, etc. `category` is
// included because several resources filter by it the same way
// (case-insensitive category name match), not because every list
// endpoint has it -- callers extend this type, they don't all use every
// field.
export interface ListParams {
  search?: string;
  category?: string;
  limit?: number;
  offset?: number;
}
