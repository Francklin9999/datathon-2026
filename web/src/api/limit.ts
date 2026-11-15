/**
 * A fetch that keeps at most `max` requests in flight, in the order they were asked for. The
 * deployed API runs with a concurrency of five (infra/README.md): a burst above it is refused with
 * 503, which then costs a retry. Requests start on the next microtask and are dropped if their
 * signal was aborted by then, so a request cancelled right away (a key change, or React running an
 * effect twice in development) never reaches the network.
 */
export function createLimitedFetch(inner: typeof fetch, max: number): typeof fetch {
  let active = 0;
  const queue: (() => void)[] = [];

  const next = () => {
    while (active < max && queue.length > 0) queue.shift()!();
  };

  return (input, init) => new Promise<Response>((resolve, reject) => {
    const signal = init?.signal ?? null;
    const start = () => {
      if (signal?.aborted) {
        reject(signal.reason ?? new DOMException('Aborted', 'AbortError'));
        return;
      }
      active += 1;
      inner(input, init).then(resolve, reject).finally(() => { active -= 1; next(); });
    };
    queueMicrotask(() => { queue.push(start); next(); });
  });
}

export const API_MAX_IN_FLIGHT = 4;
