/** Fictional locations supplied by the demonstration investor endpoint. */
import type { Profile } from '../../contracts/types';
import type { GlobePin } from './globeStyle';

export interface InvestorPlace { label: string; country: string; lat: number; lon: number }
export interface InvestorWallet extends InvestorPlace { accountId: string }
export interface InvestorMapEntry { profileId: string; name: string; investorType: string; home: InvestorPlace; wallets: InvestorWallet[] }
export interface InvestorMapResponse { investors: InvestorMapEntry[] }

/** Keep every location, including those belonging to profiles other than the selected one. */
export function investorMapPins(investors: readonly InvestorMapEntry[], profiles: readonly Pick<Profile, 'profileId' | 'accounts'>[], selectedProfileId: string): GlobePin[] {
  const accountsByProfile = new Map(profiles.map(profile => [profile.profileId, profile.accounts ?? []]));
  return investors.flatMap(investor => {
    const selected = investor.profileId === selectedProfileId;
    const common = { profileId: investor.profileId, owner: investor.name, selected };
    return [
      { id: `investor:${investor.profileId}`, kind: 'investor' as const, lat: investor.home.lat, lng: investor.home.lon,
        label: `${investor.name} · ${investor.home.label}`, countryLevel: false, weight: 0,
        investorLocation: { ...common, kind: 'home' as const, name: investor.name, location: investor.home.label, country: investor.home.country } },
      ...investor.wallets.map(wallet => {
        const name = accountsByProfile.get(investor.profileId)?.find(account => account.accountId === wallet.accountId)?.name ?? wallet.accountId;
        return { id: `wallet:${investor.profileId}:${wallet.accountId}`, kind: 'wallet' as const, lat: wallet.lat, lng: wallet.lon,
          label: `${investor.name} · ${name} · ${wallet.label}`, countryLevel: false, weight: 0,
          investorLocation: { ...common, kind: 'wallet' as const, name, location: wallet.label, country: wallet.country } };
      }),
    ];
  });
}

export function parseInvestorMap(value: unknown): InvestorMapResponse {
  const record = (v: unknown): v is Record<string, unknown> => v !== null && typeof v === 'object' && !Array.isArray(v);
  const place = (v: unknown): v is InvestorPlace => record(v) && typeof v.label === 'string' && typeof v.country === 'string'
    && typeof v.lat === 'number' && Number.isFinite(v.lat) && Math.abs(v.lat) <= 90
    && typeof v.lon === 'number' && Number.isFinite(v.lon) && Math.abs(v.lon) <= 180;
  if (!record(value) || !Array.isArray(value.investors) || !value.investors.every((item: unknown) => record(item)
    && typeof item.profileId === 'string' && typeof item.name === 'string' && typeof item.investorType === 'string'
    && place(item.home) && Array.isArray(item.wallets) && item.wallets.every((wallet: unknown) => place(wallet) && typeof (wallet as unknown as Record<string, unknown>).accountId === 'string'))) {
    throw new Error('Invalid investor map response');
  }
  return value as unknown as InvestorMapResponse;
}
