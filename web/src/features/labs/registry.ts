/**
 * The Labs tools as data: each has an id (the ?tool= value), a category, a plain name and purpose in
 * English and French, an icon and a loader that fetches its code only when it is opened. `gate` names
 * the research source family that must be available (readySource), exactly as the Markets page gated
 * its connector cards; `needsProfile` wraps the tool in ProfileGate like its original page.
 * Pure data apart from the lazy loaders, so tests/labs-registry.test.ts can import it under node.
 */
import { createElement, type ComponentType } from 'react';
import {
  Activity, BadgeCheck, Bitcoin, Building, ChartLine, ClipboardList, Coins, Crosshair, Database, Droplets, FileSearch,
  GitCompare, Globe, Grid3x3, Hash, Inbox, KeyRound, Landmark, Layers, Library, Network, Newspaper, PiggyBank, Plug,
  Radar, ScanSearch, ScrollText, Search, SlidersHorizontal, Sigma, Target, type LucideIcon,
} from 'lucide-react';
import type { I18NText, Profile } from '../../contracts/types';
import type { QueryState } from '../../state/useQuery';
import type { SourceAvailability } from '../markets/SourceAvailability';

export type LabCategoryId = 'market-research' | 'instruments' | 'risk' | 'planning' | 'comparison';

export interface LabCategory { id: LabCategoryId; label: I18NText }

type Capabilities = Parameters<typeof SourceAvailability>[0]['value'];

/** What the Labs page hands every tool. `profile` is set whenever the tool needs one. */
export interface ToolContext {
  profile: Profile | null;
  profiles: Profile[];
  ready: (sourceId: string) => boolean;
  capabilities: QueryState<NonNullable<Capabilities>>;
}

export interface LabTool {
  id: string;
  category: LabCategoryId;
  label: I18NText;
  purpose: I18NText;
  icon: LucideIcon;
  loader: () => Promise<ComponentType<ToolContext>>;
  needsProfile: boolean;
  /** Source family that must be available for the tool to show (readySource). */
  gate?: string;
  /** Reset the tool when the analysis period changes (its figures depend on it). */
  periodBound?: boolean;
}

export const LAB_CATEGORIES: readonly LabCategory[] = [
  { id: 'market-research', label: { en: 'Market research', fr: 'Recherche de marché' } },
  { id: 'instruments', label: { en: 'Instruments', fr: 'Instruments' } },
  { id: 'risk', label: { en: 'Risk lab', fr: 'Laboratoire de risque' } },
  { id: 'planning', label: { en: 'Planning', fr: 'Planification' } },
  { id: 'comparison', label: { en: 'Comparison', fr: 'Comparaison' } },
];

type Loader = LabTool['loader'];

/** A tool without props. */
const plain = (load: () => Promise<ComponentType>): Loader => () =>
  load().then(Tool => function LabTool() { return createElement(Tool); });

/** A tool that reads the selected profile (the page renders it inside ProfileGate). */
const withProfile = (load: () => Promise<ComponentType<{ profile: Profile }>>): Loader => () =>
  load().then(Tool => function LabTool({ profile }: ToolContext) { return profile ? createElement(Tool, { profile }) : null; });

export const LAB_TOOLS: readonly LabTool[] = [
  // Market research: the connector cards of the former Markets page, behind the same source gates.
  {
    id: 'source-availability', category: 'market-research', icon: Database, needsProfile: false,
    label: { en: 'Source availability', fr: 'Disponibilité des sources' },
    purpose: { en: 'Which research sources have a documented capture today', fr: 'Les sources de recherche dont une capture est documentée aujourd’hui' },
    loader: () => import('../markets/SourceAvailability').then(m => function LabTool({ capabilities }: ToolContext) {
      return createElement(m.SourceAvailability, { value: capabilities.data, loading: capabilities.loading, error: capabilities.error, reload: capabilities.reload });
    }),
  },
  {
    id: 'connected-markets', category: 'market-research', icon: Plug, needsProfile: false,
    label: { en: 'Connected market data', fr: 'Données de marché connectées' },
    purpose: { en: 'Read a quote or history from a provider you connected', fr: 'Lire un cours ou un historique chez un fournisseur connecté' },
    loader: plain(() => import('../markets/KeyedMarkets').then(m => m.KeyedMarkets)),
  },
  {
    id: 'legal-entities', category: 'market-research', icon: Building, needsProfile: false, gate: 'gleif',
    label: { en: 'Legal entities', fr: 'Entités juridiques' },
    purpose: { en: 'Find a company in the global legal entity register', fr: 'Trouver une société dans le registre mondial des entités juridiques' },
    loader: plain(() => import('../markets/EntityResearch').then(m => m.EntityResearch)),
  },
  {
    id: 'issuer-relationships', category: 'market-research', icon: Network, needsProfile: false, gate: 'gleif',
    label: { en: 'Issuer relationships', fr: 'Liens entre émetteurs' },
    purpose: { en: 'See who owns or controls an issuer, with its evidence', fr: 'Voir qui détient ou contrôle un émetteur, avec ses preuves' },
    loader: plain(() => import('../markets/IssuerEvidence').then(m => m.IssuerEvidence)),
  },
  {
    id: 'register-updates', category: 'market-research', icon: Newspaper, needsProfile: false, gate: 'golden_copy',
    label: { en: 'Register updates', fr: 'Mises à jour du registre' },
    purpose: { en: 'Recent changes published in the legal entity register', fr: 'Les changements récents publiés dans le registre des entités' },
    loader: plain(() => import('../markets/GoldenCopy').then(m => m.GoldenCopy)),
  },
  {
    id: 'wikidata', category: 'market-research', icon: Library, needsProfile: false, gate: 'wikidata',
    label: { en: 'Wikidata candidates', fr: 'Candidats Wikidata' },
    purpose: { en: 'Possible matches for a company in Wikidata, to check by hand', fr: 'Correspondances possibles d’une société dans Wikidata, à vérifier' },
    loader: plain(() => import('../markets/WikidataCandidates').then(m => m.WikidataCandidates)),
  },
  {
    id: 'provider-observations', category: 'market-research', icon: Activity, needsProfile: false, gate: 'coinmetrics',
    label: { en: 'Crypto network data', fr: 'Données des réseaux crypto' },
    purpose: { en: 'Dated network and price observations for a crypto asset', fr: 'Observations datées de réseau et de prix pour un actif crypto' },
    loader: plain(() => import('../markets/ProviderObservations').then(m => m.ProviderObservations)),
  },
  {
    id: 'on-chain', category: 'market-research', icon: Coins, needsProfile: false, gate: 'dexscreener',
    label: { en: 'On-chain markets', fr: 'Marchés sur chaîne' },
    purpose: { en: 'Trading pairs and liquidity on decentralized exchanges', fr: 'Paires et liquidité sur les plateformes décentralisées' },
    loader: plain(() => import('../markets/DefiResearch').then(m => m.DefiResearch)),
  },
  {
    id: 'crypto-history', category: 'market-research', icon: Bitcoin, needsProfile: false, gate: 'binance_vision',
    label: { en: 'Crypto exchange history', fr: 'Historique d’une plateforme crypto' },
    purpose: { en: 'Daily prices published by a crypto exchange', fr: 'Les prix quotidiens publiés par une plateforme crypto' },
    loader: plain(() => import('../markets/CryptoHistory').then(m => m.CryptoHistory)),
  },
  {
    id: 'eu-records', category: 'market-research', icon: Landmark, needsProfile: false, gate: 'eu',
    label: { en: 'European regulatory records', fr: 'Registres réglementaires européens' },
    purpose: { en: 'What European regulators publish about an entity or fund', fr: 'Ce que les régulateurs européens publient sur une entité ou un fonds' },
    loader: plain(() => import('../markets/EURegulatory').then(m => m.EURegulatory)),
  },
  {
    id: 'bitcoin-sentiment', category: 'market-research', icon: ChartLine, needsProfile: false, gate: 'sentiment',
    label: { en: 'Bitcoin sentiment', fr: 'Sentiment sur le bitcoin' },
    purpose: { en: 'A dated sentiment reading, shown as context only', fr: 'Une mesure datée du sentiment, donnée comme contexte seulement' },
    loader: plain(() => import('../markets/BitcoinSentiment').then(m => m.BitcoinSentiment)),
  },
  {
    id: 'company-registry', category: 'market-research', icon: ScrollText, needsProfile: false, gate: 'registries',
    label: { en: 'Company registries', fr: 'Registres des sociétés' },
    purpose: { en: 'Official national company records', fr: 'Les fiches officielles des registres nationaux' },
    loader: plain(() => import('../markets/CompanyRegistry').then(m => m.CompanyRegistry)),
  },
  {
    id: 'japan-research', category: 'market-research', icon: Globe, needsProfile: false, gate: 'regional',
    label: { en: 'Japan research', fr: 'Recherche sur le Japon' },
    purpose: { en: 'Prices, company facts and financials from Japanese sources', fr: 'Prix, fiches et états financiers de sources japonaises' },
    loader: () => import('../markets/RegionalResearch').then(m => function LabTool() { return createElement(m.RegionalResearch, { allowedRegions: ['JP'] }); }),
  },
  {
    id: 'korea-filings', category: 'market-research', icon: FileSearch, needsProfile: false, gate: 'opendart',
    label: { en: 'Korea filings', fr: 'Dépôts coréens' },
    purpose: { en: 'Filings, financials and ownership from the Korean regulator', fr: 'Dépôts, états financiers et actionnariat du régulateur coréen' },
    loader: () => import('../markets/RegionalResearch').then(m => function LabTool() { return createElement(m.RegionalResearch, { allowedRegions: ['KR'] }); }),
  },

  // Instruments
  {
    id: 'instruments', category: 'instruments', icon: Search, needsProfile: false,
    label: { en: 'Instrument discovery', fr: 'Recherche de titres' },
    purpose: { en: 'Search the supported instruments and read their history', fr: 'Chercher les titres pris en charge et lire leur historique' },
    loader: plain(() => import('./InstrumentDiscovery').then(m => m.InstrumentDiscovery)),
  },
  {
    id: 'instrument-master', category: 'instruments', icon: Hash, needsProfile: false, gate: 'master',
    label: { en: 'Identifier crosswalk', fr: 'Correspondance des identifiants' },
    purpose: { en: 'Match tickers, ISINs and other codes for one instrument', fr: 'Relier symboles, ISIN et autres codes d’un même titre' },
    loader: () => import('../markets/InstrumentMaster').then(m => function LabTool({ ready }: ToolContext) {
      return createElement(m.InstrumentMaster, { showCoinMetrics: ready('coinmetrics'), showWikidata: ready('wikidata') });
    }),
  },
  {
    id: 'openfigi', category: 'instruments', icon: KeyRound, needsProfile: false, gate: 'openfigi',
    label: { en: 'OpenFIGI mappings', fr: 'Correspondances OpenFIGI' },
    purpose: { en: 'Look up the global identifier of an instrument', fr: 'Trouver l’identifiant mondial d’un titre' },
    loader: plain(() => import('../markets/OpenFigi').then(m => m.OpenFigi)),
  },

  // Risk lab
  {
    id: 'focus-candidates', category: 'risk', icon: Crosshair, needsProfile: true,
    label: { en: 'Focus candidates', fr: 'Points à examiner' },
    purpose: { en: 'Holdings that stand out by fixed rules, worth a closer look', fr: 'Les positions qui ressortent selon des règles fixes, à examiner' },
    loader: withProfile(() => import('../risk/FocusCandidates').then(m => m.FocusCandidates)),
  },
  {
    id: 'covariance', category: 'risk', icon: Grid3x3, needsProfile: true, periodBound: true,
    label: { en: 'Covariance', fr: 'Covariance' },
    purpose: { en: 'How your holdings moved together over the period', fr: 'Comment vos positions ont varié ensemble sur la période' },
    loader: withProfile(() => import('../risk/ExpandedRisk').then(m => m.Covariance)),
  },
  {
    id: 'liquidity', category: 'risk', icon: Droplets, needsProfile: true,
    label: { en: 'Sale timing and liquidity', fr: 'Calendrier de vente et liquidité' },
    purpose: { en: 'How long selling could take under your assumptions', fr: 'Le temps qu’une vente pourrait prendre selon vos hypothèses' },
    loader: withProfile(() => import('../risk/ExpandedRisk').then(m => m.Liquidity)),
  },
  {
    id: 'active-factor', category: 'risk', icon: Sigma, needsProfile: true, periodBound: true,
    label: { en: 'Factor exposure', fr: 'Exposition factorielle' },
    purpose: { en: 'Which market factors your portfolio followed', fr: 'Les facteurs de marché que votre portefeuille a suivis' },
    loader: withProfile(() => import('../risk/ExpandedRisk').then(m => m.ActiveFactor)),
  },
  {
    id: 'nested-funds', category: 'risk', icon: Layers, needsProfile: false,
    label: { en: 'Funds inside funds', fr: 'Fonds dans les fonds' },
    purpose: { en: 'What you hold through nested funds, and what stays unknown', fr: 'Ce que vous détenez via des fonds imbriqués, et ce qui reste inconnu' },
    loader: plain(() => import('../risk/ExpandedRisk').then(m => m.NestedFunds)),
  },
  {
    id: 'model-inputs', category: 'risk', icon: ScanSearch, needsProfile: false,
    label: { en: 'Factor fit and fund look-through', fr: 'Ajustement factoriel et transparence des fonds' },
    purpose: { en: 'Apply the models to data you supply yourself', fr: 'Appliquer les modèles à des données que vous fournissez' },
    loader: plain(() => import('../risk/ModelInputs').then(m => m.ModelInputs)),
  },
  {
    id: 'sensitivity', category: 'risk', icon: SlidersHorizontal, needsProfile: true,
    label: { en: 'Sensitivity scenario', fr: 'Scénario de sensibilité' },
    purpose: { en: 'See the effect of the shocks you choose on your portfolio', fr: 'Voir l’effet des chocs que vous choisissez sur votre portefeuille' },
    loader: withProfile(() => import('../risk/SensitivityScenario').then(m => m.SensitivityScenario)),
  },
  {
    id: 'financial-providers', category: 'risk', icon: Radar, needsProfile: false,
    label: { en: 'Public financial feeds', fr: 'Flux financiers publics' },
    purpose: { en: 'Read a dated value from an additional public feed', fr: 'Lire une valeur datée dans un flux public supplémentaire' },
    loader: plain(() => import('../risk/FinancialProviders').then(m => m.FinancialProviders)),
  },
  {
    id: 'captured-inputs', category: 'risk', icon: Inbox, needsProfile: false,
    label: { en: 'Captured rates and positioning', fr: 'Taux et positionnement capturés' },
    purpose: { en: 'Dated rate and market positioning captures, with their sources', fr: 'Captures datées de taux et de positionnement, avec leurs sources' },
    loader: plain(() => import('../risk/FinancialInputs').then(m => m.FinancialInputs)),
  },

  // Planning
  {
    id: 'target-drift', category: 'planning', icon: Target, needsProfile: true,
    label: { en: 'Target drift', fr: 'Écart à la cible' },
    purpose: { en: 'How far your holdings sit from your target mix', fr: 'L’écart entre vos positions et la répartition visée' },
    loader: withProfile(() => import('../portfolio/AllocationTargets').then(m => m.AllocationTargets)),
  },
  {
    id: 'joint-plan', category: 'planning', icon: ClipboardList, needsProfile: true,
    label: { en: 'Goals, spending and liquidity plan', fr: 'Plan des objectifs, dépenses et liquidités' },
    purpose: { en: 'Check goals, spending and cash needs together', fr: 'Vérifier ensemble objectifs, dépenses et besoins de liquidités' },
    loader: withProfile(() => import('../planning/JointPlan').then(m => m.JointPlan)),
  },
  {
    id: 'goal-funding', category: 'planning', icon: PiggyBank, needsProfile: true,
    label: { en: 'Goal funding', fr: 'Financement des objectifs' },
    purpose: { en: 'Whether your contributions could fund each goal', fr: 'Si vos versements pourraient financer chaque objectif' },
    loader: withProfile(() => import('../portfolio/GoalFunding').then(m => m.GoalFunding)),
  },
  {
    id: 'requirements', category: 'planning', icon: BadgeCheck, needsProfile: true,
    label: { en: 'Spending and liquidity scenario', fr: 'Scénario de dépenses et de liquidité' },
    purpose: { en: 'Whether planned withdrawals stay covered over time', fr: 'Si les retraits prévus restent couverts dans le temps' },
    loader: withProfile(() => import('../portfolio/RequirementsScenario').then(m => m.RequirementsScenario)),
  },

  // Comparison
  {
    id: 'profile-compare', category: 'comparison', icon: GitCompare, needsProfile: true,
    label: { en: 'Compare profiles', fr: 'Comparer des profils' },
    purpose: { en: 'Put two saved profiles side by side', fr: 'Mettre deux profils enregistrés côte à côte' },
    loader: () => import('../profiles/ProfileCompare').then(m => function LabTool({ profiles }: ToolContext) {
      return createElement(m.ProfileCompare, { profiles });
    }),
  },
];

export const LAB_TOOL_IDS: readonly string[] = LAB_TOOLS.map(tool => tool.id);

/** The tool shown when ?tool= is missing or unknown: it needs no profile and no source gate. */
export const DEFAULT_LAB_TOOL = 'instruments';

/** Tools of one category that may show, given the source gates. */
export function visibleTools(category: LabCategoryId, ready: (sourceId: string) => boolean): LabTool[] {
  return LAB_TOOLS.filter(tool => tool.category === category && (!tool.gate || ready(tool.gate)));
}
