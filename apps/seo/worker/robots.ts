/**
 * robots.txt parsing and enforcement.
 *
 * This is a hard gate, not a courtesy. Crawling our own storefront is our
 * business; crawling a competitor's is somebody else's server, and the only
 * defensible way to do it is the way the standard describes: fetch
 * `/robots.txt` first, obey the most specific matching group, send an honest
 * identifying User-Agent, and stay slow.
 *
 * Deliberate policy choices, since the standard leaves them open:
 *
 * * **A robots.txt we cannot fetch is treated as "allowed".** That matches
 *   the RFC 9309 default for a 404, and for a 5xx we are choosing the
 *   permissive reading rather than blocking a competitor forever on one bad
 *   response. A network error is not consent withdrawn.
 * * **`Disallow: /` on our group means we stop entirely** and record the
 *   competitor as blocked, rather than retrying nightly. Repeatedly asking a
 *   site that has said no is the behaviour that gets a crawler banned.
 * * **Only `Allow`/`Disallow` are interpreted.** `Crawl-delay` is honoured by
 *   a fixed floor in the crawler instead, because a competitor asking for 30
 *   seconds per page would make a run unbounded; if their delay exceeds our
 *   budget we crawl fewer pages rather than crawl faster.
 */

export interface RobotsRules {
  /** Path prefixes we may not fetch, longest first. */
  disallow: string[];
  /** Explicit exceptions that override a broader disallow. */
  allow: string[];
  /** True when the matching group disallows everything. */
  blocksEverything: boolean;
  crawlDelaySeconds: number;
}

export const CRAWLER_USER_AGENT = "TrueGritSeoAgent";

const ALLOW_ALL: RobotsRules = {
  disallow: [],
  allow: [],
  blocksEverything: false,
  crawlDelaySeconds: 0,
};

/**
 * Parse robots.txt, keeping the group that applies to us.
 *
 * Group selection follows the standard: a group naming our agent explicitly
 * wins over the `*` group, and consecutive `User-agent` lines share one set of
 * rules. Anything we do not understand is ignored rather than guessed at.
 */
export function parseRobots(body: string, userAgent = CRAWLER_USER_AGENT): RobotsRules {
  const agent = userAgent.toLowerCase();
  const groups: Array<{ agents: string[]; rules: RobotsRules }> = [];
  let current: { agents: string[]; rules: RobotsRules } | null = null;
  let expectingAgents = false;

  for (const rawLine of body.split(/\r?\n/)) {
    const line = rawLine.split("#")[0]?.trim() ?? "";
    if (!line) continue;
    const separator = line.indexOf(":");
    if (separator === -1) continue;
    const field = line.slice(0, separator).trim().toLowerCase();
    const value = line.slice(separator + 1).trim();

    if (field === "user-agent") {
      // Consecutive user-agent lines accumulate into one group; a user-agent
      // line after any rule starts a new one.
      if (!current || !expectingAgents) {
        current = {
          agents: [],
          rules: { disallow: [], allow: [], blocksEverything: false, crawlDelaySeconds: 0 },
        };
        groups.push(current);
      }
      current.agents.push(value.toLowerCase());
      expectingAgents = true;
      continue;
    }

    if (!current) continue;
    expectingAgents = false;

    if (field === "disallow") {
      if (value === "") continue; // An empty Disallow means "allow everything".
      current.rules.disallow.push(value);
      if (value === "/") current.rules.blocksEverything = true;
    } else if (field === "allow") {
      if (value) current.rules.allow.push(value);
    } else if (field === "crawl-delay") {
      const delay = Number.parseFloat(value);
      if (Number.isFinite(delay) && delay > 0) current.rules.crawlDelaySeconds = delay;
    }
  }

  const named = groups.find((group) =>
    group.agents.some((value) => agent.includes(value) && value !== "*"),
  );
  const wildcard = groups.find((group) => group.agents.includes("*"));
  const chosen = named ?? wildcard;
  if (!chosen) return ALLOW_ALL;

  // Longest prefix wins, so `/blog/` beats `/` when both are present.
  chosen.rules.disallow.sort((a, b) => b.length - a.length);
  chosen.rules.allow.sort((a, b) => b.length - a.length);
  return chosen.rules;
}

/** Prefix match with `*` and `$`, which are the only wildcards the de-facto
 *  standard defines. */
function matches(pattern: string, path: string): boolean {
  if (!pattern.includes("*") && !pattern.includes("$")) return path.startsWith(pattern);
  const escaped = pattern
    .replace(/[.+?^${}()|[\]\\]/g, "\\$&")
    .replace(/\*/g, ".*")
    .replace(/\\\$$/, "$");
  try {
    return new RegExp(`^${escaped}`).test(path);
  } catch {
    return false;
  }
}

export function isAllowed(rules: RobotsRules, path: string): boolean {
  if (rules.blocksEverything) {
    // An explicit Allow can still carve an exception out of `Disallow: /`.
    return rules.allow.some((pattern) => matches(pattern, path));
  }
  const disallowed = rules.disallow.find((pattern) => matches(pattern, path));
  if (!disallowed) return true;
  const allowed = rules.allow.find((pattern) => matches(pattern, path));
  // A more specific Allow overrides a broader Disallow.
  return allowed !== undefined && allowed.length >= disallowed.length;
}

export async function fetchRobots(origin: string, timeoutMs = 10_000): Promise<RobotsRules> {
  try {
    const response = await fetch(`${origin}/robots.txt`, {
      headers: { "user-agent": CRAWLER_USER_AGENT },
      signal: AbortSignal.timeout(timeoutMs),
    });
    // 404 means no restrictions were published. 5xx we also treat as open
    // rather than blocking a site indefinitely on a transient failure.
    if (!response.ok) return ALLOW_ALL;
    return parseRobots(await response.text());
  } catch {
    return ALLOW_ALL;
  }
}
