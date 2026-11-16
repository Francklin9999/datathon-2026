import { strict as assert } from 'node:assert';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import type { PortfolioAccount } from '../src/contracts/types';
import { clusterPins } from '../src/features/world/globeStyle';
import { investorMapPins, parseInvestorMap } from '../src/features/world/investorMap';

const valid = { investors: [{ profileId: 'p_0000000001', name: 'Example', investorType: 'individual',
  home: { label: 'Montréal', country: 'CA', lat: 45.5, lon: -73.6 },
  wallets: [{ accountId: 'account-1', label: 'London', country: 'GB', lat: 51.5, lon: -0.1 }] }] };

test('investor map validates location and account data', () => {
  assert.deepEqual(parseInvestorMap(valid), valid);
  assert.throws(() => parseInvestorMap({ investors: [{ ...valid.investors[0], home: { ...valid.investors[0]!.home, lat: 91 } }] }));
  assert.throws(() => parseInvestorMap({ investors: [{ ...valid.investors[0], wallets: [{ label: 'London', country: 'GB', lat: 51, lon: 0 }] }] }));
});

test('all fictional residences and wallets are present regardless of selected profile', () => {
  const data = parseInvestorMap(JSON.parse(readFileSync(new URL('../../data/inputs/investor-examples/locations.json', import.meta.url), 'utf8')));
  const first = data.investors[0]!;
  const accountId = first.wallets[0]!.accountId;
  const profiles = [{ profileId: first.profileId, accounts: [{ accountId, name: 'Test account' } as PortfolioAccount] }];
  const pins = investorMapPins(data.investors, profiles, 'unrelated-profile');
  assert.equal(pins.filter(pin => pin.kind === 'investor').length, 5);
  assert.equal(pins.filter(pin => pin.kind === 'wallet').length, 15);
  assert.equal(clusterPins(pins, 2.1, null).length, 20);
  assert.ok(pins.every(pin => !pin.investorLocation?.selected));
  assert.equal(pins.find(pin => pin.id === `wallet:${first.profileId}:${accountId}`)?.investorLocation?.name, 'Test account');
  const selected = investorMapPins(data.investors, profiles, first.profileId);
  assert.equal(selected.filter(pin => pin.investorLocation?.selected).length, 4);
});
