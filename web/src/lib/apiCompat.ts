/**
 * Site/API version skew. The site and the API are deployed separately (the site on every push to
 * main, the API by an owner release), so a page can run against an API whose contract is older than
 * the one this site was built for. Pages gate a feature on the contract version the API reports in
 * `GET /meta` instead of calling a route that the API may not have yet.
 *
 * Contract versions are `major.minor.patch`. A newer minor adds routes and fields; a different major
 * is incompatible either way.
 */
import schema from '../../../contracts/generated/schema.json' with { type: 'json' };
import type { I18NText, Meta } from '../contracts/types';

/** The contract version this site was generated against (contracts/generated/schema.json). */
export const WEB_CONTRACT_VERSION: string = schema['x-contract-version'];

/**
 * First contract version that serves each gated feature. `strategies`: POST
 * /v1/profiles/{id}/strategies/simulate arrived in commit 032eb8e, which bumped the contract
 * from 1.4.0 to 1.5.0.
 */
export const FEATURE_MIN_CONTRACT = { strategies: '1.5.0' } as const;
export type GatedFeature = keyof typeof FEATURE_MIN_CONTRACT;

export interface ContractVersion { major: number; minor: number; patch: number }

/** `1.5.0` (an optional pre-release or build suffix is ignored); null when it is not a version. */
export function parseContractVersion(value: string | null | undefined): ContractVersion | null {
  const match = /^\s*v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?\s*$/.exec(value ?? '');
  if (!match) return null;
  return { major: Number(match[1]), minor: Number(match[2]), patch: Number(match[3]) };
}

/** Negative, zero or positive as `a` is older than, equal to or newer than `b`. */
export function compareContractVersions(a: ContractVersion, b: ContractVersion): number {
  return a.major - b.major || a.minor - b.minor || a.patch - b.patch;
}

/**
 * - `supported`: same major, and at least `minimumVersion`.
 * - `older`: same major, below `minimumVersion` (the feature arrives with the next API release).
 * - `incompatible`: a different major, or an unparsable version.
 * - `unknown`: `/meta` has not answered yet; show nothing yet rather than a notice.
 */
export type ApiCompatibility = 'supported' | 'older' | 'incompatible' | 'unknown';

export function apiCompatibility(meta: Pick<Meta, 'contractVersion'> | null | undefined, minimumVersion: string): ApiCompatibility {
  if (!meta) return 'unknown';
  const api = parseContractVersion(meta.contractVersion);
  const minimum = parseContractVersion(minimumVersion);
  if (!api || !minimum || api.major !== minimum.major) return 'incompatible';
  return compareContractVersions(api, minimum) >= 0 ? 'supported' : 'older';
}

/** True only when the API reports a contract that serves `minimumVersion` (false while /meta loads). */
export function apiSupports(meta: Pick<Meta, 'contractVersion'> | null | undefined, minimumVersion: string): boolean {
  return apiCompatibility(meta, minimumVersion) === 'supported';
}

/** Short status for a card or a list row whose feature the connected API does not serve yet. */
export const NEEDS_NEWER_API: I18NText = {
  en: 'Needs the newer API release',
  fr: 'Exige la nouvelle version de l’API',
};

/** One line under a notice: which contract the feature needs and which one the API reports. */
export function apiVersionLine(minimumVersion: string, apiVersion: string | null | undefined): I18NText {
  const api = apiVersion?.trim() || '—';
  return {
    en: `This feature needs API contract ${minimumVersion} or later; the connected API reports ${api}.`,
    fr: `Cette fonction exige le contrat d’API ${minimumVersion} ou plus récent ; l’API connectée indique ${api}.`,
  };
}
