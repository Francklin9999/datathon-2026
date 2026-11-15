/**
 * Tour scripts. The basic tour shows the shell and the dashboard; each advanced tour walks through
 * one use case on its page. Targets are `data-tour` attributes placed in the components.
 */
import type { Tour } from '../../lib/tour/engine';

export const BASIC_TOUR: Tour = {
  id: 'basics',
  route: '/',
  title: { en: 'Discover Aplomb', fr: 'Découvrir Aplomb' },
  summary: { en: 'The essentials in one minute.', fr: 'L’essentiel en une minute.' },
  steps: [
    {
      id: 'welcome', route: '/',
      title: { en: 'Welcome to Aplomb', fr: 'Bienvenue dans Aplomb' },
      body: {
        en: 'Aplomb tests hypothetical moves against a fictional investor’s plan. Code computes every figure, AI explains, and every figure links to its source.',
        fr: 'Aplomb teste des mouvements hypothétiques sur le plan d’un investisseur fictif. Le code calcule chaque chiffre, l’IA explique, et chaque chiffre renvoie à sa source.',
      },
    },
    {
      id: 'persona', route: '/', target: 'persona',
      title: { en: 'Pick a fictional investor', fr: 'Choisissez un investisseur fictif' },
      body: { en: 'Each profile has its own portfolio and rules. Switch here and every page follows.', fr: 'Chaque profil a son portefeuille et ses règles. Changez-le ici : toutes les pages suivent.' },
    },
    {
      id: 'command', route: '/', target: 'command',
      title: { en: 'Ask in plain words', fr: 'Demandez en langage courant' },
      body: {
        en: 'Type a move such as “add 5% of NVDA”, or say it with the microphone if your browser shows one, check the words and press Enter. It opens in Decide, where nothing runs until you confirm. Shortcut: /',
        fr: 'Tapez un mouvement comme « ajouter 5 % de NVDA », ou dites-le avec le micro si votre navigateur en affiche un, vérifiez les mots puis Entrée. Il s’ouvre dans Décider, où rien ne s’exécute avant votre confirmation. Raccourci : /',
      },
    },
    {
      id: 'rail', route: '/', target: 'rail', placement: 'right', optional: true,
      title: { en: 'Move between pages', fr: 'Passez d’une page à l’autre' },
      body: {
        en: 'Home, Portfolio, Decide, World, Evidence, Replay and System. Hover an icon for its name; the arrow at the bottom shows the labels.',
        fr: 'Accueil, Portefeuille, Décider, Monde, Preuves, Rejouer et Système. Survolez une icône pour son nom ; la flèche du bas affiche les libellés.',
      },
    },
    {
      id: 'scope', route: '/', target: 'scope',
      title: { en: 'Set the period', fr: 'Réglez la période' },
      body: { en: 'The period and the benchmark change every figure on the dashboard.', fr: 'La période et l’indice de comparaison changent tous les chiffres du tableau de bord.' },
    },
    {
      id: 'kpis', route: '/', target: 'kpis', optional: true,
      title: { en: 'Key figures', fr: 'Les chiffres clés' },
      body: {
        en: 'A figure with a dotted underline opens its source: how it was computed, over which period, from which data.',
        fr: 'Un chiffre souligné en pointillé ouvre sa source : comment il est calculé, sur quelle période, avec quelles données.',
      },
    },
    {
      id: 'health', route: '/', target: 'health', optional: true,
      title: { en: 'Plan health', fr: 'La santé du plan' },
      body: {
        en: 'The verdict counts the rules that fit, are under tension or conflict. Missing evidence is listed apart.',
        fr: 'Le verdict compte les règles respectées, en tension ou en conflit. Les preuves manquantes sont listées à part.',
      },
    },
    {
      id: 'dock', route: '/', target: 'dock', placement: 'top', optional: true,
      title: { en: 'Jump to a section', fr: 'Sautez à une section' },
      body: { en: 'The dock lists the sections of the page. The + button tests a move from anywhere.', fr: 'Le dock liste les sections de la page. Le bouton + teste un mouvement depuis n’importe où.' },
    },
    {
      id: 'disclaimer', route: '/', target: 'disclaimer',
      title: { en: 'Always a simulation', fr: 'Toujours une simulation' },
      body: { en: 'Fictional profiles, no real order, no financial advice.', fr: 'Profils fictifs, aucun ordre réel, aucun conseil financier.' },
    },
    {
      id: 'settings', route: '/', target: 'settings',
      title: { en: 'Language and theme', fr: 'Langue et thème' },
      body: { en: 'Switch between English and French, light and dark.', fr: 'Passez du français à l’anglais, du clair au sombre.' },
    },
    {
      id: 'help', route: '/', target: 'help',
      title: { en: 'Replay the tutorials', fr: 'Revoyez les tutoriels' },
      body: {
        en: 'This button replays this tour and offers one tutorial per use case.',
        fr: 'Ce bouton relance cette visite et propose un tutoriel par cas d’usage.',
      },
    },
  ],
};

const t = (en: string, fr: string) => ({ en, fr });

export const ADVANCED_TOURS: readonly Tour[] = [
  {
    id: 'dashboard', route: '/',
    title: t('Read the dashboard', 'Lire le tableau de bord'),
    summary: t('Period, history, allocation, plan health and the brief.', 'Période, historique, répartition, santé du plan et note.'),
    steps: [
      { id: 'scope', route: '/', target: 'scope', title: t('One scope for every widget', 'Un périmètre pour tout le tableau'),
        body: t('Pick a period or a custom range, a benchmark, asset classes or a minimum weight. The “i” says which widgets each choice changes.', 'Choisissez une période ou des dates, un indice, des classes d’actifs ou un poids minimum. Le « i » indique ce que chaque choix modifie.') },
      { id: 'performance', route: '/', target: 'performance', optional: true, title: t('Past performance', 'Performance passée'),
        body: t('Today’s weights applied to past prices. Hover the line to compare any date; “Show table” gives the same numbers as a table.', 'Les pondérations actuelles appliquées aux prix passés. Survolez la courbe pour comparer une date ; « Afficher le tableau » donne les mêmes chiffres.') },
      { id: 'allocation', route: '/', target: 'allocation', optional: true, title: t('Allocation', 'Répartition'),
        body: t('Switch between asset classes and countries. Hover a slice or a row to pair them.', 'Basculez entre classes d’actifs et pays. Survolez une part ou une ligne pour les relier.') },
      { id: 'positions', route: '/', target: 'positions', optional: true, title: t('Largest positions', 'Les plus grosses positions'),
        body: t('Sorted by weight. “All holdings” opens the full table in Portfolio.', 'Triées par poids. « Toutes les positions » ouvre le tableau complet dans Portefeuille.') },
      { id: 'health', route: '/', target: 'health', optional: true, title: t('Rules nearest their limit', 'Les règles proches de leur limite'),
        body: t('The rules with the least room left come first, with the value against the limit. Each figure opens its source.', 'Les règles avec le moins de marge viennent d’abord, avec la valeur face à la limite. Chaque chiffre ouvre sa source.') },
      { id: 'brief', route: '/', target: 'brief', optional: true, title: t('The portfolio brief', 'La note de portefeuille'),
        body: t('An AI-written summary, audited sentence by sentence. Every number in it links to the ledger; “Refresh brief” writes a new one.', 'Un résumé rédigé par l’IA et audité phrase par phrase. Chaque nombre renvoie au registre ; « Actualiser la note » en rédige une nouvelle.') },
      { id: 'layout', route: '/', target: 'edit-layout', optional: true, title: t('Arrange your dashboard', 'Arrangez votre tableau de bord'),
        body: t('Turn on layout editing, then drag widgets by their handle or resize them from the corner. Arrow keys work too.', 'Activez la modification, puis glissez les widgets par leur poignée ou redimensionnez-les par le coin. Les flèches fonctionnent aussi.') },
    ],
  },
  {
    id: 'decide', route: '/decision-desk/',
    title: t('Test a move', 'Tester un mouvement'),
    summary: t('From a sentence to an audited verdict.', 'D’une phrase à un verdict audité.'),
    steps: [
      { id: 'header', route: '/decision-desk/', target: 'desk-header', title: t('Decide', 'Décider'),
        body: t('Test a hypothetical move against the selected investor’s rules. The period on the right sets the risk window.', 'Testez un mouvement hypothétique contre les règles de l’investisseur choisi. La période à droite fixe la fenêtre de risque.') },
      { id: 'freetext', route: '/decision-desk/', target: 'freetext', title: t('Describe it in words', 'Décrivez-le en mots'),
        body: t('Write the move and press Interpret. The AI proposes an interpretation; “Use in the form” fills the fields below.', 'Écrivez le mouvement puis Interpréter. L’IA propose une interprétation ; « Utiliser dans le formulaire » remplit les champs.') },
      { id: 'form', route: '/decision-desk/', target: 'move-form', title: t('Or fill in the form', 'Ou remplissez le formulaire'),
        body: t('Choose the asset and how it is funded: automatically, from new money, or from holdings you pick.', 'Choisissez l’actif et son financement : automatique, nouvel apport ou positions que vous choisissez.') },
      { id: 'size', route: '/decision-desk/', target: 'move-size', title: t('Set the size', 'Réglez la taille'),
        body: t('The amount added, in points of today’s value — not a target weight. The check on the right updates as you slide.', 'Le montant ajouté, en points de la valeur actuelle — pas un poids cible. La vérification à droite suit le curseur.') },
      { id: 'preview', route: '/decision-desk/', target: 'preview', title: t('Instant rule check', 'Vérification instantanée'),
        body: t('Computed by code, with no AI: the verdict, the count per status and the largest size before the first rule conflict.', 'Calculée par le code, sans IA : le verdict, le nombre par statut et la taille maximale avant le premier conflit.') },
      { id: 'analyze', route: '/decision-desk/', target: 'analyze', title: t('Analyze the evidence', 'Analysez les preuves'),
        body: t('Starts the audited AI analysis: scenarios, funding options and a brief whose every sentence is checked.', 'Lance l’analyse IA auditée : scénarios, options de financement et une note dont chaque phrase est vérifiée.') },
      { id: 'compare', route: '/decision-desk/', target: 'compare', optional: true, title: t('Compare two investors', 'Comparez deux investisseurs'),
        body: t('Run the same move on another profile: different rules can give different verdicts.', 'Appliquez le même mouvement à un autre profil : des règles différentes peuvent donner d’autres verdicts.') },
    ],
  },
  {
    id: 'plan', route: '/portfolio/',
    title: t('Adjust the plan', 'Ajuster le plan'),
    summary: t('Holdings, correlations and editable rules.', 'Positions, corrélations et règles modifiables.'),
    steps: [
      { id: 'holdings', route: '/portfolio/', target: 'holdings', title: t('Holdings', 'Positions'),
        body: t('Every position with its class, weight, value and one-year return.', 'Chaque position avec sa classe, son poids, sa valeur et son rendement sur un an.') },
      { id: 'risk', route: '/portfolio/', target: 'risk', title: t('Risk and correlations', 'Risque et corrélations'),
        body: t('In the heatmap, orange means two holdings move together and blue means they move apart. Hover a cell to read it in words.', 'Dans la carte de chaleur, l’orange signifie que deux positions évoluent ensemble, le bleu qu’elles s’opposent. Survolez une case pour la lire en mots.') },
      { id: 'rules', route: '/portfolio/', target: 'rules', title: t('Edit a rule', 'Modifiez une règle'),
        body: t('Change a threshold, press Preview to see the new verdict, then Save. Earlier briefs are then marked out of date.', 'Changez un seuil, Aperçu pour voir le nouveau verdict, puis Enregistrer. Les notes antérieures sont alors marquées périmées.') },
      { id: 'frontier', route: '/portfolio/', target: 'frontier', optional: true, title: t('Risk/return frontier', 'Frontière risque/rendement'),
        body: t('Loaded on demand. It describes the past sample; clicking a point only inspects its weights.', 'Chargée à la demande. Elle décrit l’échantillon passé ; cliquer un point montre seulement ses pondérations.') },
    ],
  },
  {
    id: 'evidence', route: '/evidence-audit/',
    title: t('Check the evidence', 'Vérifier les preuves'),
    summary: t('Sources, audit marks and the sabotage test.', 'Sources, marques d’audit et test de sabotage.'),
    steps: [
      { id: 'runs', route: '/evidence-audit/', target: 'run-list', title: t('Your analyses', 'Vos analyses'),
        body: t('Every analysis started in this session. Filter by state, then open one.', 'Toutes les analyses lancées dans cette session. Filtrez par état, puis ouvrez-en une.') },
      { id: 'inside', route: '/evidence-audit/', title: t('Inside an analysis', 'Dans une analyse'),
        body: t('You see the brief with its audit marks, the audit report, the rule checks, then folded: the fact ledger, the evidence, the steps and the data used.', 'Vous voyez la note avec ses marques d’audit, le rapport d’audit, les vérifications, puis repliés : le registre des faits, les preuves, les étapes et les données.') },
      { id: 'facts', route: '/evidence-audit/', title: t('Follow any figure', 'Suivez n’importe quel chiffre'),
        body: t('Click a figure with a dotted underline: a panel shows how it was computed, from which data, and which sentences use it.', 'Cliquez un chiffre souligné en pointillé : un panneau montre son calcul, ses données et les phrases qui l’utilisent.') },
      { id: 'sabotage', route: '/evidence-audit/', title: t('The sabotage test', 'Le test de sabotage'),
        body: t('On a finished decision, start a labelled copy where the writer is told to lie, and see whether the auditor catches it.', 'Sur une décision terminée, lancez une copie identifiée où le rédacteur reçoit l’ordre de mentir, et voyez si l’auditeur le détecte.') },
    ],
  },
  {
    id: 'world', route: '/world-explorer/',
    title: t('Explore world events', 'Explorer les événements mondiaux'),
    summary: t('Sourced events linked to the holdings.', 'Des événements sourcés liés aux positions.'),
    steps: [
      { id: 'header', route: '/world-explorer/', target: 'world-header', title: t('World', 'Monde'),
        body: t('Events from the loaded dataset, each with its source. A link to a holding is a documented match, never an impact estimate.', 'Des événements du jeu de données, chacun avec sa source. Un lien avec une position est une correspondance documentée, jamais une estimation d’impact.') },
      { id: 'filters', route: '/world-explorer/', target: 'world-filters', optional: true, title: t('Filter', 'Filtrez'),
        body: t('Keep only events linked to the portfolio, or open more filters: dates, countries, categories and sources.', 'Gardez seulement les événements liés au portefeuille, ou ouvrez d’autres filtres : dates, pays, catégories et sources.') },
      { id: 'feed', route: '/world-explorer/', target: 'world-feed', optional: true, title: t('The feed', 'Le fil'),
        body: t('Pick an event to see its sources, the holdings it touches and why. “Brief me” writes an audited explanation.', 'Choisissez un événement pour voir ses sources, les positions concernées et pourquoi. « Rédiger une note » écrit une explication auditée.') },
      { id: 'globe', route: '/world-explorer/', target: 'world-globe', optional: true, title: t('The globe', 'Le globe'),
        body: t('Another view of the same events. Click a pin or a country; everything is also in the feed.', 'Une autre vue des mêmes événements. Cliquez une épingle ou un pays ; tout figure aussi dans le fil.') },
    ],
  },
  {
    id: 'replay', route: '/time-machine/',
    title: t('Replay history', 'Rejouer l’histoire'),
    summary: t('Decide at a past date, then reveal what followed.', 'Décider à une date passée, puis révéler la suite.'),
    steps: [
      { id: 'warning', route: '/time-machine/', target: 'tm-warning', optional: true, title: t('Know the limits', 'Connaissez les limites'),
        body: t('The AI still knows what happened later, and prices are adjusted. Read this note once before you replay.', 'L’IA connaît encore la suite et les prix sont ajustés. Lisez cette note une fois avant de rejouer.') },
      { id: 'cutoff', route: '/time-machine/', target: 'tm-cutoff', optional: true, title: t('Pick a cutoff date', 'Choisissez une date limite'),
        body: t('Choose a suggested date or type one. Only data available on that day is used.', 'Choisissez une date proposée ou saisissez-en une. Seules les données disponibles ce jour-là sont utilisées.') },
      { id: 'move', route: '/time-machine/', target: 'move-form', optional: true, title: t('Set the move', 'Définissez le mouvement'),
        body: t('The same form as in Decide: asset, funding and size.', 'Le même formulaire que dans Décider : actif, financement et taille.') },
      { id: 'start', route: '/time-machine/', target: 'tm-start', optional: true, title: t('Run, then reveal', 'Lancez, puis révélez'),
        body: t('Run the replay to get the verdict at that date. Then reveal what happened next; the original verdict never changes.', 'Lancez le rejeu pour obtenir le verdict à cette date. Révélez ensuite la suite ; le verdict d’origine ne change jamais.') },
    ],
  },
  {
    id: 'system', route: '/agents-system/',
    title: t('See what ran', 'Voir ce qui a tourné'),
    summary: t('Roles, recorded steps and configuration.', 'Rôles, étapes enregistrées et configuration.'),
    steps: [
      { id: 'header', route: '/agents-system/', target: 'system-header', title: t('System', 'Système'),
        body: t('Code computes the figures and verdicts; AI plans, researches and writes. This page separates the two.', 'Le code calcule les chiffres et verdicts ; l’IA planifie, cherche et rédige. Cette page sépare les deux.') },
      { id: 'roles', route: '/agents-system/', target: 'roles', title: t('Who may do what', 'Qui peut faire quoi'),
        body: t('Each role, whether it is AI or code, and the tools it is allowed to use.', 'Chaque rôle, s’il s’agit d’IA ou de code, et les outils qu’il peut utiliser.') },
      { id: 'runs', route: '/agents-system/', target: 'system-runs', title: t('What an analysis recorded', 'Ce qu’une analyse a enregistré'),
        body: t('Open an analysis to see each step: who did it, the model, tokens, tool calls and what failed.', 'Ouvrez une analyse pour voir chaque étape : qui l’a faite, le modèle, les jetons, les appels d’outil et les échecs.') },
    ],
  },
  {
    id: 'data', route: '/sources/',
    title: t('Profiles and data sources', 'Profils et sources de données'),
    summary: t('Create an investor and check where data comes from.', 'Créer un investisseur et voir d’où viennent les données.'),
    steps: [
      { id: 'profiles', route: '/profiles/', target: 'profiles-header', optional: true, title: t('Fictional profiles', 'Profils fictifs'),
        body: t('Copy a default profile, fill in the form, or describe an investor in words and confirm the proposed fields.', 'Copiez un profil par défaut, remplissez le formulaire, ou décrivez un investisseur en mots et confirmez les champs proposés.') },
      { id: 'sources', route: '/sources/', target: 'sources-header', title: t('Data sources', 'Sources de données'),
        body: t('Each dataset’s provider, licence, retrieval date and coverage. Open one for its schema and quality checks.', 'Pour chaque jeu de données : fournisseur, licence, date de récupération et couverture. Ouvrez-en un pour son schéma et ses contrôles.') },
      { id: 'traps', route: '/sources/', target: 'traps', optional: true, title: t('Known traps', 'Pièges connus'),
        body: t('Calendar gaps, adjusted prices, survivor bias… and whether each is handled, disclosed or still open.', 'Calendriers, prix ajustés, biais du survivant… et si chacun est traité, signalé ou encore ouvert.') },
    ],
  },
];

export const ALL_TOURS: readonly Tour[] = [BASIC_TOUR, ...ADVANCED_TOURS];
