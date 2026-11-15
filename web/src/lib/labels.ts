/**
 * Bilingual labels for every catalog code the UI displays (contracts/catalog.md: "the i18n
 * dictionaries of the web app must contain a label for every code"). `Record<Code, …>` makes the
 * compiler reject a missing code; tests/labels.test.ts checks against the runtime catalog too.
 */
import type {
  AgentRole, AssetClass, AssetGroup, AuditCheckCode, CountryExposure, ErrorCode, EventCategory, EventLocation,
  EventSource, EvidenceType, Experience, Facility, FactKind, FeatureFlag, FundingMode, Hazard, HoldingExposure,
  I18NText, Lang, LimitationCode, NeeReason, Objective, RiskLevel, RuleStatus, RunKind, RunStatus, SabotageMode,
  ScenarioKind, StepType, ThemeTag, Verdict, WindowCode, WorldEvent, WorldLayer,
} from '../contracts/types';

export type Labels<K extends string> = Record<K, I18NText>;
const l = (en: string, fr: string): I18NText => ({ en, fr });

export const VERDICT: Labels<Verdict> = {
  compatible: l('Fits the rules', 'Compatible avec les règles'),
  tension: l('Tension', 'Tension'),
  conflict: l('Conflict', 'Conflit'),
  insufficient: l('Not enough evidence', 'Preuves insuffisantes'),
};

export const RULE_STATUS: Labels<RuleStatus> = {
  pass: l('Fit', 'Conforme'),
  tension: l('Tension', 'Tension'),
  conflict: l('Conflict', 'Conflit'),
  nee: l('Not enough evidence', 'Preuves insuffisantes'),
  info: l('Information', 'Information'),
};

export const RUN_STATUS: Labels<RunStatus> = {
  queued: l('Queued', 'En file'),
  running: l('Running', 'En cours'),
  waiting_input: l('Waiting for your answer', 'En attente de votre réponse'),
  succeeded: l('Done', 'Terminée'),
  failed: l('Failed', 'Échec'),
  cancelled: l('Cancelled', 'Annulé'),
};

export const RUN_KIND: Labels<RunKind> = {
  decision: l('Decision audit', 'Audit de décision'),
  rebalance: l('Target allocation review', 'Examen de la répartition cible'),
  portfolio_brief: l('Portfolio brief', 'Note de portefeuille'),
  event_brief: l('Event brief', "Note d'événement"),
  replay: l('Historical replay', 'Rejeu historique'),
  profile_draft: l('Profile draft', 'Brouillon de profil'),
  sabotage: l('Sabotage demonstration', 'Démonstration de sabotage'),
};

export const STEP_TYPE: Labels<StepType> = {
  plan: l('Plan', 'Plan'),
  research: l('Research', 'Recherche'),
  quant: l('Calculations', 'Calculs'),
  risk_check: l('Rule check', 'Vérification des règles'),
  revise: l('Revision', 'Révision'),
  write: l('Write', 'Rédaction'),
  audit: l('Audit', 'Audit'),
  sign: l('Sign', 'Signature'),
};

export const AGENT_ROLE: Labels<AgentRole> = {
  planner: l('Planner', 'Planificateur'),
  researcher: l('Researcher', 'Chercheur'),
  quant: l('Quant', 'Quant'),
  risk_officer: l('Risk officer', 'Responsable des risques'),
  writer: l('Writer', 'Rédacteur'),
  auditor: l('Auditor', 'Auditeur'),
};

export const ACTOR: Labels<'llm' | 'llm+tools' | 'code' | 'code+llm'> = {
  llm: l('Language model', 'Modèle de langage'),
  'llm+tools': l('Language model with tools', 'Modèle de langage avec outils'),
  code: l('Code', 'Code'),
  'code+llm': l('Code and language model', 'Code et modèle de langage'),
};

export const FACT_KIND: Labels<FactKind> = {
  observed: l('Observed', 'Observé'),
  computed: l('Computed', 'Calculé'),
  assumption: l('Assumption', 'Hypothèse'),
  input: l('Your input', 'Votre saisie'),
  scenario: l('Hypothetical scenario', 'Scénario hypothétique'),
  rule_check: l('Rule check', 'Vérification de règle'),
  evidence: l('Quoted evidence', 'Preuve citée'),
};

export const FUNDING_MODE: Labels<FundingMode> = {
  auto: l('Compare funding options', 'Comparer les sources de financement'),
  pro_rata: l('Pro-rata from all holdings', 'Au prorata de toutes les positions'),
  from_cash: l('From cash', "À partir de l'encaisse"),
  from_holdings: l('From named holdings', 'À partir de positions nommées'),
  new_money: l('New money', 'Nouvel apport'),
};

export const RISK_LEVEL: Labels<RiskLevel> = {
  low: l('Low', 'Faible'),
  low_moderate: l('Low to moderate', 'Faible à modéré'),
  moderate: l('Moderate', 'Modéré'),
  moderate_high: l('Moderate to high', 'Modéré à élevé'),
  high: l('High', 'Élevé'),
};

export const OBJECTIVE: Labels<Objective> = {
  preserve: l('Preserve capital', 'Préserver le capital'),
  balanced: l('Balanced', 'Équilibré'),
  growth: l('Growth', 'Croissance'),
};

export const EXPERIENCE: Labels<Experience> = {
  beginner: l('Beginner', 'Débutant'),
  intermediate: l('Intermediate', 'Intermédiaire'),
  advanced: l('Advanced', 'Avancé'),
};

export const ASSET_GROUP: Labels<AssetGroup> = {
  equity: l('Equity', 'Actions'),
  fixed_income: l('Fixed income', 'Revenu fixe'),
  commodity: l('Commodities', 'Matières premières'),
  crypto: l('Crypto', 'Crypto'),
  cash: l('Cash', 'Encaisse'),
};

export const ASSET_CLASS: Labels<AssetClass> = {
  equity: l('Single stock', 'Action individuelle'),
  etf_equity: l('Equity ETF', 'FNB actions'),
  etf_bond: l('Bond ETF', 'FNB obligataire'),
  etf_commodity: l('Commodity ETF', 'FNB matières premières'),
  crypto: l('Crypto asset', 'Cryptoactif'),
  cash: l('Cash', 'Encaisse'),
};

export const WINDOW: Labels<WindowCode> = {
  full: l('Full sample', 'Échantillon complet'),
  '1y': l('1 year', '1 an'),
  '3y': l('3 years', '3 ans'),
  '5y': l('5 years', '5 ans'),
  ytd: l('Year to date', 'Depuis le début de l’année'),
  custom: l('Custom window', 'Fenêtre personnalisée'),
};

export const NEE_REASON: Labels<NeeReason> = {
  short_history: l('Too little price history in the window', 'Historique de prix trop court dans la fenêtre'),
  no_evidence_loaded: l('No research evidence is attached', 'Aucune preuve documentaire n’est jointe'),
  evidence_unverified: l('Evidence could not be verified', 'La preuve n’a pas pu être vérifiée'),
  not_visible_at_asof: l('Data needed lies after the selected date', 'Les données nécessaires sont postérieures à la date choisie'),
  asset_unknown: l('Asset could not be resolved', 'L’actif n’a pas pu être identifié'),
  dataset_missing: l('A required dataset is not loaded', 'Un jeu de données requis n’est pas chargé'),
};

export const LIMITATION: Labels<LimitationCode> = {
  LIM_PAST_NOT_FUTURE: l('Past performance does not guarantee future results. These figures describe a historical sample; they are not forecasts.',
    'Les rendements passés ne garantissent pas les rendements futurs. Ces chiffres décrivent un échantillon historique ; ce ne sont pas des prévisions.'),
  LIM_SAMPLE_WINDOW: l('Computed on the available window only (from 2021-11-12 in the starter data). Other periods would give different values.',
    'Calculé sur la seule fenêtre disponible (depuis le 2021-11-12 dans les données de départ). D’autres périodes donneraient d’autres valeurs.'),
  LIM_SURVIVORSHIP: l('The asset universe was chosen in 2026 among names that are large today, which flatters historical results.',
    'L’univers d’actifs a été choisi en 2026 parmi des titres aujourd’hui importants, ce qui flatte les résultats historiques.'),
  LIM_CONSTANT_WEIGHTS: l('Portfolio history applies today’s weights to past returns, rebalanced daily. It is not what an actual investor would have earned.',
    'L’historique applique les pondérations actuelles aux rendements passés, rééquilibrées chaque jour. Ce n’est pas ce qu’un investisseur réel aurait obtenu.'),
  LIM_FX_FFILL: l('USD/CAD uses the Bank of Canada daily rate; on days without a published rate the previous rate is carried forward.',
    'Le USD/CAD utilise le taux quotidien de la Banque du Canada ; les jours sans taux publié, le taux précédent est reporté.'),
  LIM_CALENDAR_INTERSECTION: l('Only days when both the Canadian and US markets were open are used; crypto weekend moves appear on the next trading day.',
    'Seuls les jours d’ouverture communs aux marchés canadien et américain sont utilisés ; les variations crypto du week-end apparaissent le jour ouvrable suivant.'),
  LIM_YAHOO_NOT_CERTIFIED: l('Prices come from Yahoo Finance and are not exchange-certified. Adjusted closes change when data is re-downloaded.',
    'Les prix proviennent de Yahoo Finance et ne sont pas certifiés par une bourse. Les clôtures ajustées changent lors d’un nouveau téléchargement.'),
  LIM_CNQ_FACTOR: l('Yahoo reports a 1.021 "split" for CNQ.TO on 2022-08-22, the day of a 0.75 CAD dividend. It likely reflects a special distribution; not confirmed with the company.',
    'Yahoo indique un « fractionnement » de 1,021 pour CNQ.TO le 2022-08-22, jour d’un dividende de 0,75 CAD. Il reflète probablement une distribution spéciale ; non confirmé auprès de la société.'),
  LIM_ETF_NO_LOOKTHROUGH: l('Funds are treated as single diversified positions; their underlying holdings are not counted in sector or single-name limits.',
    'Les fonds sont traités comme des positions diversifiées uniques ; leurs titres sous-jacents ne sont pas comptés dans les limites sectorielles ou par titre.'),
  LIM_SECTOR_LABELS: l('Sector labels for starter assets were assigned by the organizers and are simplified.',
    'Les secteurs des actifs de départ ont été attribués par les organisateurs et sont simplifiés.'),
  LIM_THEME_TAGS: l('Theme tags are team assumptions documented per asset; they are not an official classification.',
    'Les thèmes sont des hypothèses de l’équipe documentées par actif ; ce n’est pas une classification officielle.'),
  LIM_THRESHOLDS_ASSUMED: l('Rule thresholds are assumptions derived from the stated risk level and horizon. They are editable and are not regulatory limits.',
    'Les seuils des règles sont des hypothèses tirées du niveau de risque et de l’horizon déclarés. Ils sont modifiables et ne sont pas des limites réglementaires.'),
  LIM_BONDS_SAMPLE: l('In the 2021–2026 sample bonds were unusually volatile, which affects thresholds derived from it.',
    'Dans l’échantillon 2021–2026, les obligations ont été inhabituellement volatiles, ce qui influence les seuils qui en découlent.'),
  LIM_MACRO_REVISED: l('US macro values are the latest revised figures, not as first published.',
    'Les valeurs macroéconomiques américaines sont les dernières révisées, pas celles publiées initialement.'),
  LIM_MACRO_LAG_ASSUMED: l('Publication dates of monthly macro data are approximated with a fixed lag.',
    'Les dates de publication des données macro mensuelles sont approximées par un délai fixe.'),
  LIM_NO_CONTROVERSY_DATA: l('No controversy or ESG rating dataset is loaded. Absence of evidence is not evidence of absence.',
    'Aucun jeu de données de controverses ou de notation ESG n’est chargé. L’absence de preuve n’est pas la preuve de l’absence.'),
  LIM_EVIDENCE_TIER: l('Some sources are not official or established publishers and are shown for context only.',
    'Certaines sources ne sont pas des éditeurs officiels ou reconnus et ne sont montrées qu’à titre de contexte.'),
  LIM_IMPACT_NOT_ESTABLISHED: l('A link between an event and a holding was identified; its financial impact was not measured.',
    'Un lien entre un événement et une position a été repéré ; son impact financier n’a pas été mesuré.'),
  LIM_PRICE_MOVE_NOT_CAUSAL: l('A price change after an event is an observation, not proof that the event caused it.',
    'Une variation de prix après un événement est une observation, pas la preuve que l’événement l’a causée.'),
  LIM_LLM_KNOWLEDGE: l('The language model may know what happened after the selected date. Numbers come from date-filtered data, but wording could reflect later knowledge.',
    'Le modèle de langage peut savoir ce qui s’est passé après la date choisie. Les chiffres viennent de données filtrées par date, mais la formulation pourrait refléter des connaissances ultérieures.'),
  LIM_SHORT_HISTORY: l('At least one asset has too little history for reliable risk figures.',
    'Au moins un actif a un historique trop court pour des mesures de risque fiables.'),
  LIM_CASH_NO_INTEREST: l('Cash is modelled with zero return and zero volatility.',
    'L’encaisse est modélisée avec un rendement et une volatilité nuls.'),
  LIM_SIMULATION_ONLY: l('Simulation with fictional profiles and portfolios. Not financial advice. No order is placed.',
    'Simulation avec des profils et portefeuilles fictifs. Ceci n’est pas un conseil financier. Aucun ordre n’est passé.'),
  LIM_ATTENTION_PROXY: l('Page views measure public attention, not investment quality.',
    'Les consultations de pages mesurent l’attention du public, pas la qualité d’un placement.'),
  LIM_REGISTRY_MATCH: l('Facilities are matched to companies by name; some matches may be wrong or missing.',
    'Les installations sont associées aux sociétés par leur nom ; certaines correspondances peuvent être fausses ou manquantes.'),
  LIM_STRATEGY_COSTS: l('Trading costs are the flat rate per traded amount you set. Taxes, bid-ask spreads and whole-share limits are not modelled.',
    'Les frais sont le taux fixe par montant échangé que vous choisissez. Impôts, écarts acheteur-vendeur et parts entières ne sont pas modélisés.'),
  LIM_STRATEGY_EXECUTION: l('Actions are applied at the closing price of the day the trigger is observed. Real orders would execute later, at other prices.',
    'Les actions sont appliquées au cours de clôture du jour où le déclencheur est constaté. De vrais ordres seraient exécutés plus tard, à d’autres prix.'),
  LIM_MV_ILLUSTRATION: l('Mean-variance points use past average returns as inputs and are shown for illustration only.',
    'Les points moyenne-variance utilisent les rendements moyens passés et ne sont montrés qu’à titre d’illustration.'),
};

/** Short descriptions of audit checks A01–A14 (catalog.md §6). */
export const AUDIT_CHECK: Labels<AuditCheckCode> = {
  A01: l('Every reference points to an existing fact, rule or evidence item', 'Chaque référence renvoie à un fait, une règle ou une preuve existants'),
  A02: l('No numbers outside referenced values', 'Aucun chiffre hors des valeurs référencées'),
  A03: l('Stated comparisons are true for the referenced facts', 'Les comparaisons énoncées sont vraies pour les faits référencés'),
  A04: l('Every facts sentence cites a fact or evidence item', 'Chaque phrase de faits cite un fait ou une preuve'),
  A05: l('Mandatory sections present (facts, assumptions, limits)', 'Sections obligatoires présentes (faits, hypothèses, limites)'),
  A06: l('Simulation disclaimer present', 'Avertissement de simulation présent'),
  A07: l('No banned phrasing (instructions, guarantees, predictions)', 'Aucune formulation interdite (instructions, garanties, prédictions)'),
  A08: l('Quoted passages found in the cached source document', 'Citations retrouvées dans le document source en cache'),
  A09: l('No interpretation unsupported by cited facts or evidence', 'Aucune interprétation non étayée par les faits ou preuves cités'),
  A10: l('Guardrail did not block the text', 'Le garde-fou n’a pas bloqué le texte'),
  A11: l('Every fact was available at the run’s information date', 'Chaque fait était disponible à la date d’information de l’exécution'),
  A12: l('Assumptions section mentions every rule in conflict or tension', 'La section hypothèses mentionne chaque règle en conflit ou en tension'),
  A13: l('Limits section lists every limitation of cited facts', 'La section limites énumère chaque limite des faits cités'),
  A14: l('Impact statements only with a measured price move', 'Énoncés d’impact seulement avec une variation de prix mesurée'),
};

export const ERROR_CODE: Labels<ErrorCode> = {
  validation_error: l('The request was not valid', 'La requête n’est pas valide'),
  not_found: l('Not found', 'Introuvable'),
  conflict: l('Conflict with the current version', 'Conflit avec la version actuelle'),
  forbidden_action: l('Not available: this is a simulation and no orders are placed', 'Non disponible : ceci est une simulation et aucun ordre n’est passé'),
  insufficient_data: l('Not enough data for this calculation', 'Données insuffisantes pour ce calcul'),
  rate_limited: l('Too many requests; retrying more slowly', 'Trop de requêtes ; nouvel essai plus lent'),
  upstream_unavailable: l('Service unavailable', 'Service indisponible'),
  feature_disabled: l('This feature is turned off', 'Cette fonction est désactivée'),
  internal: l('Unexpected server error', 'Erreur inattendue du serveur'),
};

export const CLIENT_ERROR: Labels<'network' | 'invalid_response' | 'aborted'> = {
  network: l('Could not reach the API', 'Impossible de joindre l’API'),
  invalid_response: l('The API answered with an unexpected shape', 'L’API a répondu dans un format inattendu'),
  aborted: l('Request cancelled', 'Requête annulée'),
};

export const EVIDENCE_TYPE: Labels<EvidenceType> = {
  filing: l('Regulatory filing', 'Dépôt réglementaire'),
  company_report: l('Company report', 'Rapport de société'),
  fund_document: l('Fund document', 'Document de fonds'),
  official_release: l('Official release', 'Communiqué officiel'),
  news: l('News', 'Actualité'),
  registry: l('Registry', 'Registre'),
  attention: l('Attention data', 'Données d’attention'),
  web_page: l('Web page', 'Page web'),
};

export const SCENARIO_KIND: Labels<ScenarioKind> = {
  requested: l('Requested move', 'Mouvement demandé'),
  max_compatible: l('Largest size before the first rule conflict', 'Taille maximale avant le premier conflit'),
  alternative: l('Alternative', 'Solution de rechange'),
  goal_candidate: l('Goal candidate', 'Candidat pour l’objectif'),
  rebalance: l('Rebalance', 'Rééquilibrage'),
};

export const SABOTAGE_MODE: Labels<SabotageMode> = {
  invented_number: l('Invented number', 'Chiffre inventé'),
  false_comparison: l('False comparison', 'Fausse comparaison'),
  unsupported_interpretation: l('Unsupported interpretation', 'Interprétation non étayée'),
};

export const DATASET_STATUS: Labels<'in_use' | 'planned' | 'rejected'> = {
  in_use: l('In use', 'Utilisé'),
  planned: l('Planned', 'Prévu'),
  rejected: l('Rejected', 'Rejeté'),
};

export const TRAP_STATUS: Labels<'handled' | 'disclosed' | 'open'> = {
  handled: l('Handled', 'Traité'),
  disclosed: l('Disclosed', 'Divulgué'),
  open: l('Open', 'Ouvert'),
};

export const VERIFICATION: Labels<'verified' | 'unverified' | 'failed'> = {
  verified: l('Verified', 'Vérifié'),
  unverified: l('Unverified', 'Non vérifié'),
  failed: l('Failed verification', 'Échec de vérification'),
};

export const SENTENCE_AUDIT: Labels<'verified' | 'struck' | 'repaired'> = {
  verified: l('Verified', 'Vérifiée'),
  struck: l('Struck by the auditor', 'Rayée par l’auditeur'),
  repaired: l('Repaired', 'Corrigée'),
};

// ----- World Explorer (T15, contracts/schemas.md §10) -----

export const EVENT_CATEGORY: Labels<EventCategory> = {
  monetary_policy: l('Monetary policy', 'Politique monétaire'),
  macro_release: l('Macro data release', 'Publication macroéconomique'),
  geopolitical: l('Geopolitics', 'Géopolitique'),
  trade_regulation: l('Trade and regulation', 'Commerce et réglementation'),
  corporate: l('Corporate', 'Entreprises'),
  energy_commodities: l('Energy and commodities', 'Énergie et matières premières'),
  markets: l('Markets', 'Marchés'),
  natural_disaster: l('Natural disaster', 'Catastrophe naturelle'),
  other: l('Other', 'Autre'),
};

export const EVENT_ORIGIN: Labels<WorldEvent['origin']> = {
  gdelt: l('GDELT news index (cached batch)', 'Index de nouvelles GDELT (lot en cache)'),
  official: l('Official source', 'Source officielle'),
  curated: l('Curated from loaded datasets', 'Sélection tirée des jeux de données chargés'),
  eonet: l('NASA EONET natural events', 'Événements naturels NASA EONET'),
  usgs: l('USGS earthquake feed', 'Flux sismique USGS'),
  firms: l('NASA FIRMS fire detections', 'Détections d’incendies NASA FIRMS'),
  live: l('Live lookup', 'Recherche en direct'),
};

export const SOURCE_TYPE: Labels<EventSource['sourceType']> = {
  news: l('News', 'Presse'),
  official: l('Official', 'Officielle'),
  filing: l('Regulatory filing', 'Dépôt réglementaire'),
  data: l('Data series', 'Série de données'),
};

export const LOCATION_PRECISION: Labels<EventLocation['precision']> = {
  point: l('Exact point', 'Point exact'),
  city: l('City-level location', 'Localisation à l’échelle de la ville'),
  country: l('Country-level location (country centroid, not an exact place)', 'Localisation à l’échelle du pays (centroïde du pays, pas un lieu exact)'),
};

/** Why a holding is listed next to an event: the documented basis of the link, never an impact. */
export const LINK_TYPE: Labels<HoldingExposure['linkType']> = {
  named_in_source: l('Named in the source', 'Nommé dans la source'),
  listing_country: l('Listed in the event’s country (proxy)', 'Coté dans le pays de l’événement (approximation)'),
  sector: l('Same sector (proxy)', 'Même secteur (approximation)'),
  theme: l('Shared theme tag (team assumption)', 'Thème partagé (hypothèse de l’équipe)'),
  documented_exposure: l('Exposure documented by evidence', 'Exposition documentée par une preuve'),
  etf_lookthrough: l('Through a fund’s published holdings', 'Par les titres publiés d’un fonds'),
};

export const EXPOSURE_IMPACT: Labels<HoldingExposure['impact']> = {
  not_established: l('Financial impact not established', 'Impact financier non établi'),
  measured_price_move: l('Price change observed after the event (not proof of cause)', 'Variation de prix observée après l’événement (pas une preuve de cause)'),
};

export const EXPOSURE_BASIS: Labels<CountryExposure['basis']> = {
  listing_country: l('Listing country (proxy)', 'Pays de cotation (approximation)'),
  etf_lookthrough: l('Fund look-through', 'Transparence des fonds'),
  mixed: l('Listing country and fund look-through', 'Pays de cotation et transparence des fonds'),
};

export const WORLD_LAYER: Labels<WorldLayer['layerId']> = {
  events: l('Events', 'Événements'),
  exposure: l('Portfolio exposure by country', 'Exposition du portefeuille par pays'),
  facilities: l('Emissions facilities', 'Installations émettrices'),
  // Fallback only: the page shows the API's own layer title, which says what is loaded (earthquakes
  // today). This label must not name a hazard type the dataset may not contain.
  hazards: l('Natural hazards', 'Aléas naturels'),
  airports: l('Airports · static reference', 'Aéroports · référence statique'),
};

export const MATCH_CONFIDENCE: Labels<Facility['matchConfidence']> = {
  exact: l('Exact issuer match', 'Correspondance exacte avec l’émetteur'),
  probable: l('Probable match (uncertain)', 'Correspondance probable (incertaine)'),
  none: l('No issuer matched', 'Aucun émetteur associé'),
};

export const HAZARD_TYPE: Labels<Hazard['type']> = {
  earthquake: l('Earthquake', 'Séisme'),
  wildfire: l('Wildfire', 'Incendie de forêt'),
};

export const REGISTRY: Labels<Facility['registry']> = {
  eccc_ghgrp: l('Canada GHGRP (ECCC)', 'PDGES du Canada (ECCC)'),
  epa_ghgrp: l('US EPA GHGRP', 'GHGRP de l’EPA (États-Unis)'),
};

export const THEME_TAG: Labels<ThemeTag> = {
  ai: l('Artificial intelligence', 'Intelligence artificielle'),
  semiconductors: l('Semiconductors', 'Semi-conducteurs'),
  software: l('Software', 'Logiciels'),
  cloud: l('Cloud', 'Infonuagique'),
  ecommerce: l('E-commerce', 'Commerce en ligne'),
  electric_vehicles: l('Electric vehicles', 'Véhicules électriques'),
  big_tech: l('Big tech', 'Géants technologiques'),
  banks: l('Banks', 'Banques'),
  insurance: l('Insurance', 'Assurance'),
  fossil_energy: l('Fossil energy', 'Énergies fossiles'),
  pipelines: l('Pipelines', 'Pipelines'),
  utilities: l('Utilities', 'Services publics'),
  rail_transport: l('Rail transport', 'Transport ferroviaire'),
  consumer_staples: l('Consumer staples', 'Biens de consommation de base'),
  healthcare: l('Healthcare', 'Santé'),
  retail: l('Retail', 'Commerce de détail'),
  broad_canada: l('Broad Canadian market', 'Marché canadien élargi'),
  broad_us: l('Broad US market', 'Marché américain élargi'),
  nasdaq_growth: l('Nasdaq growth', 'Croissance Nasdaq'),
  esg_screened: l('ESG-screened', 'Filtré ESG'),
  bonds_canada: l('Canadian bonds', 'Obligations canadiennes'),
  bonds_us: l('US bonds', 'Obligations américaines'),
  long_treasuries: l('Long US Treasuries', 'Bons du Trésor américain à long terme'),
  cash_like: l('Cash-like', 'Quasi-espèces'),
  gold: l('Gold', 'Or'),
  crypto: l('Crypto', 'Crypto'),
  dividend_payers: l('Dividend payers', 'Titres à dividendes'),
};

// ----- Agents & System (T15) -----

export const FEATURE_FLAG: Labels<FeatureFlag> = {
  bilingual: l('English and French', 'Anglais et français'),
  world_explorer: l('World Explorer', 'Explorateur mondial'),
  world_layer_facilities: l('World layer: emissions facilities', 'Couche mondiale : installations émettrices'),
  world_layer_hazards: l('World layer: natural hazards', 'Couche mondiale : aléas naturels'),
  time_machine: l('Time Machine', 'Machine à remonter le temps'),
  profile_creator: l('Profile creator', 'Création de profils'),
  goal_requests: l('Goal requests', 'Requêtes par objectif'),
  sabotage_demo: l('Sabotage demonstration', 'Démonstration de sabotage'),
  research_open_web: l('Open-web research', 'Recherche sur le Web ouvert'),
  guardrails: l('Bedrock Guardrails', 'Garde-fous Bedrock'),
  on_demand_tickers: l('On-demand tickers', 'Symboles à la demande'),
  frontier_chart: l('Frontier chart', 'Graphique de frontière'),
};

export function pick(text: I18NText, lang: Lang): string {
  return text[lang] || text.en;
}

/** Look up a label; unknown codes are humanised rather than shown raw. */
export function labelOf<K extends string>(table: Labels<K>, code: string, lang: Lang): string {
  const entry = (table as Record<string, I18NText | undefined>)[code];
  if (entry) return pick(entry, lang);
  return code.replace(/[_.]+/g, ' ').replace(/^\w/, c => c.toUpperCase());
}
