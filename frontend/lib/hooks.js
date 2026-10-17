"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, errorMessage } from "@/lib/api";

export function useDebounced(value, delay) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

function asApiError(err) {
  return err instanceof ApiError ? err : new ApiError(0, errorMessage(err));
}

export function useLoad(fetcher, deps) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let active = true;
    setState((s) => ({ ...s, loading: true, error: null }));
    fetcher().then(
      (data) => { if (active) setState({ data, error: null, loading: false }); },
      (err) => { if (active) setState({ data: null, error: asApiError(err), loading: false }); },
    );
    return () => { active = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, version]);

  const reload = useCallback(() => setVersion((v) => v + 1), []);
  return { ...state, reload };
}

export function usePagedList(fetchPage, deps) {
  const [state, setState] = useState({ rows: [], cursor: null, loading: true, loadingMore: false, error: null });
  const [version, setVersion] = useState(0);
  const latest = useRef(fetchPage);

  useEffect(() => {
    latest.current = fetchPage;
  });

  useEffect(() => {
    let active = true;
    setState({ rows: [], cursor: null, loading: true, loadingMore: false, error: null });
    latest.current(null).then(
      (page) => { if (active) setState({ rows: page.items, cursor: page.next_cursor, loading: false, loadingMore: false, error: null }); },
      (err) => { if (active) setState((s) => ({ ...s, loading: false, error: errorMessage(err) })); },
    );
    return () => { active = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, version]);

  const loadMore = useCallback(async () => {
    if (!state.cursor || state.loadingMore) return;
    setState((s) => ({ ...s, loadingMore: true, error: null }));
    try {
      const page = await latest.current(state.cursor);
      setState((s) => ({ ...s, rows: [...s.rows, ...page.items], cursor: page.next_cursor, loadingMore: false }));
    } catch (err) {
      setState((s) => ({ ...s, loadingMore: false, error: errorMessage(err) }));
    }
  }, [state.cursor, state.loadingMore]);

  const reload = useCallback(() => setVersion((v) => v + 1), []);
  return { ...state, hasMore: state.cursor !== null, loadMore, reload };
}
