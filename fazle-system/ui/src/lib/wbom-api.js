"use client";

import { useSession } from "next-auth/react";
import { useCallback, useRef, useEffect } from "react";

const BASE = "/api/wbom";

export function useWbomApi() {
  const { data: session } = useSession();
  const tokenRef = useRef(session?.accessToken);

  useEffect(() => {
    tokenRef.current = session?.accessToken;
  }, [session?.accessToken]);

  const request = useCallback(async (path, options = {}) => {
    const url = `${BASE}${path}`;
    const hdrs = { "Content-Type": "application/json" };
    if (tokenRef.current) hdrs.Authorization = `Bearer ${tokenRef.current}`;
    const res = await fetch(url, {
      ...options,
      headers: { ...hdrs, ...options.headers },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  }, []);

  const get = useCallback((path) => request(path), [request]);

  const post = useCallback((path, body) =>
    request(path, { method: "POST", body: JSON.stringify(body) }),
  [request]);

  const put = useCallback((path, body) =>
    request(path, { method: "PUT", body: body ? JSON.stringify(body) : undefined }),
  [request]);

  const del = useCallback((path) =>
    request(path, { method: "DELETE" }),
  [request]);

  return { get, post, put, del };
}
