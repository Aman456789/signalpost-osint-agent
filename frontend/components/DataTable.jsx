import { EmptyState } from "@/components/EmptyState";
import { ErrorBanner } from "@/components/ErrorBanner";

// columns: [{ key, header, render(row), sortKey?, align?: "right" }]
export function DataTable(props) {
  const { columns, rows, rowKey, caption, loading, error, sort, onSortChange, onRowClick, filter } = props;
  const hasRows = rows.length > 0;

  return (
    <div className="stack">
      {(filter || props.toolbar) && (
        <div className="toolbar">
          {filter && (
            <>
              <label htmlFor="table-filter" className="label">{filter.label}</label>
              <input
                id="table-filter"
                type="search"
                className="input"
                placeholder={filter.placeholder}
                value={filter.value}
                onChange={(e) => filter.onChange(e.target.value)}
              />
            </>
          )}
          {props.toolbar}
        </div>
      )}

      {error && <ErrorBanner message={error} onRetry={props.onRetry} />}
      {loading && !hasRows && <p role="status" className="muted">Loading…</p>}
      {!loading && !error && !hasRows && <EmptyState title={props.emptyTitle}>{props.emptyText}</EmptyState>}

      {hasRows && (
        <div className="table-wrap">
          <table className="data">
            <caption className="visually-hidden">{caption}</caption>
            <thead>
              <tr>
                {columns.map((col) => {
                  const key = col.sortKey;
                  const active = key !== undefined && sort?.key === key;
                  const ariaSort = !key ? undefined : active ? (sort.order === "asc" ? "ascending" : "descending") : "none";
                  return (
                    <th key={col.key} scope="col" aria-sort={ariaSort} className={col.align === "right" ? "right" : undefined}>
                      {key && onSortChange ? (
                        <button type="button" className="sort-btn" onClick={() => onSortChange(key)}>
                          {col.header}
                          <span aria-hidden="true">{active ? (sort.order === "asc" ? " ▲" : " ▼") : ""}</span>
                        </button>
                      ) : (
                        col.header
                      )}
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={rowKey(row)}
                  className={onRowClick ? "clickable" : undefined}
                  tabIndex={onRowClick ? 0 : undefined}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  onKeyDown={onRowClick ? (e) => { if (e.key === "Enter") onRowClick(row); } : undefined}
                >
                  {columns.map((col) => (
                    <td key={col.key} className={col.align === "right" ? "right" : undefined}>{col.render(row)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {props.hasMore && props.onLoadMore && (
        <button type="button" className="btn" onClick={props.onLoadMore} disabled={props.loadingMore}>
          {props.loadingMore ? "Loading…" : "Load more"}
        </button>
      )}
    </div>
  );
}
