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
        en: 'Type a move such as “add 5% of NVDA” and press Enter. It opens in Decide, where nothing runs until you confirm. Shortcut: /',
        fr: 'Tapez un mouvement comme « ajouter 5 % de NVDA » puis Entrée. Il s’ouvre dans Décider, où rien ne s’exécute avant votre confirmation. Raccourci : /',
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

export const ADVANCED_TOURS: readonly Tour[] = [];

export const ALL_TOURS: readonly Tour[] = [BASIC_TOUR, ...ADVANCED_TOURS];
