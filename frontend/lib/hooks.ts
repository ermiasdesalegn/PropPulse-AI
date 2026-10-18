"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import type { Integrations } from "./types";

/** Fetch `path` on mount (and every `intervalMs` if given). */
export function useApi<T>(path: string | null, intervalMs?: number) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const load = useCallback(
    (isCancelled: () => boolean = () => false) =>
      path
        ? api<T>(path)
            .then(
              (result) => {
                if (isCancelled()) return;
                setData(result);
                setError(null);
              },
              (e: Error) => {
                if (!isCancelled()) setError(e.message);
              },
            )
            .finally(() => {
              if (!isCancelled()) setLoading(false);
            })
        : Promise.resolve(),
    [path],
  );

  useEffect(() => {
    let cancelled = false;
    const isCancelled = () => cancelled;
    load(isCancelled);
    const id = intervalMs ? setInterval(() => load(isCancelled), intervalMs) : undefined;
    return () => {
      cancelled = true;
      if (id) clearInterval(id);
    };
  }, [load, intervalMs]);

  const reload = useCallback(() => load(), [load]);

  return { data, error, loading, reload, setData };
}

let integrationsCache: Promise<Integrations> | null = null;

export function useIntegrations(): Integrations | null {
  const [data, setData] = useState<Integrations | null>(null);
  useEffect(() => {
    integrationsCache ??= api<Integrations>("api/admin/integrations").catch((e) => {
      integrationsCache = null;
      throw e;
    });
    integrationsCache.then(setData).catch(() => setData(null));
  }, []);
  return data;
}
