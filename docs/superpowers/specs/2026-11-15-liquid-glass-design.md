# Aplomb — nettoyage, refonte « Liquid Glass » et tutoriel rejouable — design

**Date :** 2026-11-15 · **Remplace :** [passe unslop](2026-11-15-unslop-dashboard-design.md) · **Suivi :** [progression](../plans/2026-11-15-liquid-glass.md) · **Références :** 3 captures de template fournies par l'utilisateur (Reports, Good morning, Activity)

## Contexte

Le front-end (`web/`, Next.js 16 / React 19, export statique, FR/EN) est riche mais bavard : disclaimers en double, méta techniques (version de contrat, environnement, `dataVersion`), longues notes de portée, titres jargonneux. L'utilisateur veut :
1. alléger toutes les pages (enlever, replier ou reformuler) pour réduire la charge de travail ;
2. une refonte moderne façon Apple Liquid Glass, qui suit le template fourni (3 captures « Reports / Good morning / Activity ») adapté à Aplomb (palette, menus, sidebar) ;
3. un tutoriel moderne rejouable (visite de base + tutoriels avancés par cas d'usage) ;
4. des pushes à chaque checkpoint, sur la branche `feat/liquid-glass`, puis une PR vers main (un push sur main redéploie CloudFront via `deploy-site.yml`).

Note d'historique : un style verre avait été fait le 14/11 puis retiré le 15/11 par la passe « unslop » d'un coéquipier (fond uni, graphite + cobalt). Cette refonte le remplace à la demande explicite de l'utilisateur ; `web/DESIGN.md` sera réécrit en conséquence.

## Lecture du template → transposition Aplomb

| Template | Aplomb |
|---|---|
| Barre supérieure flottante sombre : avatar + « Welcome, Code XR » | Sélecteur d'investisseur fictif (avatar initiale + nom, liste déroulante, « Gérer les profils ») |
| Barre de commande IA centrale avec orbe (« Can you send $250… ») | Barre « Demander à Aplomb » : texte libre envoyé au Pupitre de décision (`/requests/parse` existant) via `/decision-desk/?q=…` ; repli formulaire manuel si le modèle est indisponible |
| Bouton rond à droite | Bouton Aide (tutoriels) + bouton Réglages (langue, thème, menu déplié) dans un popover |
| Rail vertical flottant d'icônes avec infobulles, actif = disque blanc | Navigation principale (7 pages + Sources en bas), infobulles ; dépliable en libellés (préférence `aplomb.pref.sidebar` conservée) |
| Grand panneau de verre contenant la page, titre fort + sous-titre, segmenté « This week / month / year », bouton sombre « Export CSV » | Panneau de page : titre, une phrase utile, à droite la fenêtre d'analyse (1A/3A/5A…) en segmenté et l'action principale de la page |
| Tuiles KPI : pastille d'icône teintée, libellé, gros chiffre, puce de variation | Chiffres clés (valeur, rendement, volatilité, baisse max), chiffre sourcé cliquable (FactChip) |
| Carte accentuée teal « Total Earnings » | Une seule carte cobalt : la valeur du portefeuille (l'élément mémorable) |
| Graphique en aire « Income vs expenses » + donut avec barres de légende | Historique de performance (LineChart en aire) + répartition (DonutChart avec barres de légende) |
| Table avec puces de filtre (All / Completed…), recherche, export ; « Live feed » à droite | Tables (positions, exécutions dans Preuves, règles) avec puces de filtre ; fil d'étapes (RunTimeline) en colonne |
| Dock flottant bas : onglets texte + bouton « + » | Dock des sections de la page courante (défilement vers l'ancre, section active suivie) + « + » = « Tester un mouvement » (Pupitre). Caché si la page a moins de 3 sections. Sur mobile, le rail devient une barre d'onglets en bas et le dock de sections disparaît |

## Direction visuelle (système de jetons)

- **Matière** : verre clair « liquide » — `backdrop-filter: blur(28px) saturate(170%)`, liseré spéculaire (dégradé de bordure en masque + `inset` 1 px haut), ombre douce en profondeur. Réfraction SVG (`feDisplacementMap`) seulement sur le rail, la barre du haut et le dock (Chromium ; ailleurs repli flou). Un seul flou par couche : le panneau de page floute, les cartes à l'intérieur sont du blanc translucide sans flou propre (performance).
- **Fond** (ce que le verre réfracte) : papier millimétré très fin (monde « instruments d'arpentage » d'Aplomb) + deux nappes de lumière cobalt et aqua, fixes. Pas de photo.
- **Palette clair** : fond `#ECEFF5`, verre panneau `rgba(255,255,255,.58)`, carte `rgba(255,255,255,.74)` (repli opaque `#FFFFFF`), chrome graphite `rgba(22,22,26,.78)` avec texte `#F4F4F6`, texte `#171717 / #4B4B52 / #63636B`, accent cobalt `#2F5BFF` (action principale, série suivie, carte mise en avant), statuts inchangés (vert/ambre/rouge en texte + icône).
- **Palette sombre** : fond `#0B0D12`, verre panneau `rgba(30,32,38,.55)`, carte `rgba(44,46,54,.55)`, chrome `rgba(255,255,255,.10)`, accent texte `#93AAFF`.
- **Typo** : Instrument Sans variable (local via `@fontsource-variable/instrument-sans`, repli Geist si absent) pour toute l'interface, titres 600 grands et serrés comme le template ; chiffres en `tabular-nums` dans la même famille ; IBM Plex Mono gardé uniquement pour tickers et identifiants. Fraunces et Plex Sans retirés.
- **Formes** : panneau 28, carte 20, contrôle 12, pilules entièrement arrondies (rail, dock, segmentés, puces).
- **Mouvement** : une seule courbe ; la pilule active glisse (rail, dock, segmentés — `useSlidingPill` existant) ; une entrée unique au chargement ; rien en boucle ; tout coupé sous `prefers-reduced-motion`. `prefers-reduced-transparency` et `@supports not (backdrop-filter)` → surfaces opaques.
- **Contraste** : les jetons opaques testés par `tests/ui-contrast.test.ts` (`--bg`, `--surface`, `--raised`, `--deep`) restent des hex opaques = composite approximatif du verre ; les jetons de verre sont séparés (`--glass-panel`, `--glass-card`, `--glass-chrome`…). Le parseur du test exige `:root {` et `html[data-theme='dark'] {` sans bloc imbriqué.

## Nettoyage de l'information (principes + liste)

Principes : une phrase utile maximum sous chaque titre ; le disclaimer de simulation une seule fois, toujours visible ; aucune info de développeur (version de contrat, environnement, `dataVersion`, IDs de run, IDs de modèle, hash) dans les vues normales — repliées dans « Détails techniques » sur Preuves et Système ; notes de portée et limitations repliées derrière une icône « i » ou un `<details>` ; noms de pages courts.

Le texte est écrit en ligne (`tr({ en, fr })`) dans chaque composant ; `lib/labels.ts` ne porte que les codes. Chaque reformulation se fait donc dans le fichier concerné, en FR et EN.

**Transversal (plus fort impact)**
- Disclaimer « Simulation uniquement… » ~6 fois par écran → une seule fois dans le shell (pastille persistante de la barre du haut, texte complet accessible) + celui de chaque note (vérifié par l'audit A06). Supprimer : pied de page (`AppShell.tsx:248`), note des positions (`PortfolioPage.tsx:112`), phrase du financement (`Results.tsx:164`), sous-titres Décider et Profils.
- Méta développeur → supprimée ou repliée dans « Détails techniques » : `dataVersion` (`AppShell.tsx:204`), « Contrat x, env » (`:250`), ID de requête des erreurs (`States.tsx:47-49`), ID de modèle des notes (`BriefView.tsx:83-85`), ID de run (`RunTimeline.tsx:68`, Preuves, Système), chemins d'API dans les libellés de portée du tiroir (« (/check, no model) »…), version du jeu d'événements (Monde).
- « Polling paused after an error; retrying with backoff. » ×4 → « Connexion perdue, nouvel essai… ».
- « Pas une preuve d'impact financier » ~10 fois dans Monde → une fois par événement (WUI-04).
- « Pondérations actuelles maintenues » ×4 sur l'Accueil → une seule légende sous les chiffres clés.
- Fenêtre d'analyse affichée là où elle ne sert pas → seulement sur Portefeuille et Décider (l'Accueil a sa barre de portée).
- Notes de fixtures par carte ×7 → seulement la bannière du shell.
- Listes d'exécutions en double (Preuves `RunList` et Système `RunPicker`) → un composant partagé.
- Table des règles surchargée → code fondu dans la phrase, détails (« Piloté par », preuves, formule) dans un `<details>`.
- Vocabulaire unifié : « Note de portefeuille » (au lieu de 3 noms), « Étapes » (au lieu de « Trace d'exécution »), « Analyse » (au lieu de run/exécution), pas de « déterministe » ni « signé » dans les vues normales.
- Sourcils (eyebrows) au-dessus des titres supprimés partout ; codes bruts (ISO, `LIM_*`, clés de champs, enums de thèmes, IDs de scénario) remplacés par leurs libellés ou retirés.

**Shell** : navigation raccourcie — Accueil, Portefeuille, Décider, Monde, Preuves, Rejouer, Système (EN : Home, Portfolio, Decide, World, Evidence, Replay, System) ; « Sources et passeports » → « Sources » ; « Fenêtre » → « Période » ; puces « Données au… » et « CAD, risque… » → sous-titre du panneau de l'Accueil, en une phrase ; « Connexion à l'API Aplomb… » → « Chargement… » ; bannière fixtures réduite à sa 1re phrase.

**Accueil** : retirer le sourcil, le doublon du risque, « lu depuis la série tracée », les notes de Horizons/Stress, la ligne HHI, les compteurs à zéro, les préfixes de codes de règle, « Focus n ». Titre perf → « Performance passée aux pondérations actuelles ». Note de portée de la barre et de la note → infobulle « i ». Phrases « cartes déterministes… » → « Les chiffres ci-dessus restent valables ».

**Portefeuille** : sous-titre → « {capital} de capital fictif » ; risque → « Risque historique » ; aides du tuile 2022 → infobulle ; liste MinVar/MV → `<details>` fermé ; règles → « Règles du plan », « Aperçu non enregistré » ; limitations de page repliées ; code de fenêtre brut de la légende corrigé. La matrice de corrélation reste visible et devient une carte de chaleur (voir ci-dessous).

**Matrice de corrélation en carte de chaleur** (`PortfolioPage.tsx:157-174`, demande explicite)
- Échelle divergente à deux pôles et milieu neutre (règle dataviz : jamais d'arc-en-ciel, jamais de teinte au milieu) : **−1 = cobalt** (l'accent de l'app : « évoluent en sens inverse », ce qui diversifie), **0 = gris neutre du verre** (« indépendants »), **+1 = corail chaud** (« évoluent ensemble », ce qui concentre le risque). C'est la convention la plus répandue (bleu froid / rouge chaud) et elle colle au sens financier. Le corail est choisi distinct du rouge « conflit » et de l'ambre « tension », réservés aux statuts.
- Couleur de chaque cellule calculée par intensité : `color-mix(in oklab, var(--corr-pos|neg) calc(|r| × 100%), var(--corr-mid))`. Jetons `--corr-neg`, `--corr-mid`, `--corr-pos` définis séparément pour clair et sombre (pas une inversion automatique), avec un léger verre pour se fondre dans les panneaux. Rampe vérifiée avec `validate_palette.js` du skill dataviz : luminosité monotone sur chaque bras, contraste contre les surfaces des deux thèmes.
- Les valeurs restent écrites dans les cellules (texte en jetons de texte ; il passe en clair automatiquement quand |r| est élevé, pour rester lisible AA). La diagonale (corrélation d'un actif avec lui-même = 1) est atténuée pour ne pas dominer.
- Légende en barre de dégradé sous la matrice : « −1 sens inverse », « 0 indépendants », « +1 ensemble ». Infobulle par cellule : « NVDA et TSLA : 0,62, évoluent souvent ensemble ». Mise en évidence de la ligne et de la colonne au survol et au focus clavier. Le tableau reste la vue accessible (en-têtes `scope`).

**Décider** : sous-titre → « Décrivez un mouvement ou remplissez le formulaire, puis analysez les preuves. » ; retirer « Confiance : 0.82 » et clés mono ; « Détails du mouvement », « Vérification instantanée des règles », « Lance l'analyse IA auditée » ; ID de scénario et tag répété retirés ; comparaison repliée (« Comparer avec un autre profil ») ; détails d'aperçu masqués quand l'analyse a réussi (doublon).

**Monde** : sous-titre unique portant la mise en garde d'impact ; retirer note de filtre, version du jeu, note du globe, coordonnées, nombre de sources, ligne de jeu de données, code ISO ; pieds de tableau → infobulles ; libellés courts (« Lié au portefeuille », « {n} sur {total} événements », « Note d'événement », « Masquer »).

**Preuves** : retirer IDs de run, profil, version, langue de l'en-tête ; registre, preuves, étapes, jeux de données en sections repliables (note, rapport d'audit, règles visibles) ; mise en garde « Réussi » → « Ne couvre que les vérifications ci-dessous » ; lignes techniques du tiroir de source sous « Détails techniques ».

**Rejouer** : titre → « Rejouer un mouvement à une date passée » ; avertissement obligatoire en une ligne + puces repliables (ouvert à la 1re visite) ; dates ISO, aides et ID de requête retirés ; panneau de filtrage par date et registre repliés ; texte de révélation raccourci.

**Système** (page de transparence exigée par la spec : on replie plutôt qu'on supprime) : identité de version en fin de page repliée ; listes d'outils, architecture, budget repliés ; colonne « Flag » brute retirée ; un seul affichage des étapes (pas `RunTimeline` + `StepDetail`).

**Profils** : clés de champs et enums affichés en libellés ; « Nom », « Notes », « Secteurs exclus » ; version retirée du titre.

**Sources** : « Sources de données » ; colonnes Fréquence/Lignes/Version → dans le passeport ; codes `LIM_*` retirés ; dates formatées ; schéma et traitements repliés.

Garde-fous (critères d'acceptation des page-specs à ne pas casser) : disclaimer visible sur chaque page (WEB-02, HOME-04), chaque chiffre généré ouvre sa source (FactChip), verdicts et statuts toujours icône + texte, « impact financier non établi », légendes/unités hors infobulle, alternative tableau aux graphiques, mentions obligatoires de la frontière (passé ≠ futur), avertissements de la Machine à remonter le temps (repliables mais présents avant l'analyse).

## Tutoriel (moteur maison, sans dépendance)

- `src/features/tour/` : `TourProvider` (contexte : `start(id)`, `stop`, étape courante, préférence `aplomb.pref.tour.v1`), `TourOverlay` (portail au niveau `body` : projecteur découpé autour de la cible via masque SVG, bulle en verre ancrée avec placement auto haut/bas/gauche/droite et repli centré, points de progression, Précédent / Suivant / Passer, clavier ←/→/Échap, piège de focus, retour du focus, annonce `aria-live`), `tours.ts` (définitions typées : `route`, `target` = `[data-tour="…"]`, titre/texte `{en, fr}`, `placement`, `advanceOn?: 'click'`), `HelpMenu` (bouton « ? » de la barre du haut : liste des tutoriels, état fait/pas fait, « Rejouer la visite »).
- Navigation entre pages par `router.push` puis attente de la cible (MutationObserver, délai max ~4 s) ; cible absente (drapeau de fonctionnalité éteint, API indisponible) → étape affichée centrée avec une note, ou sautée si marquée `optional`.
- Cibles posées par attributs `data-tour` sur le shell et les pages (pas de sélecteurs CSS fragiles).
- Premier lancement : fenêtre d'accueil « Découvrir Aplomb en 1 minute » (Commencer / Plus tard) ; rejouable à tout moment depuis « ? ».
- **Visite de base** (~9 étapes) : investisseur fictif → barre « Demander à Aplomb » → navigation → fenêtre d'analyse → chiffres clés et chiffre sourcé → santé du plan → dock de sections + « + » → réglages (langue, thème) → bouton Aide.
- **Tutoriels avancés** (5–8 étapes chacun) : Lire son tableau de bord (portée, édition de la disposition, analyse) ; Tester un mouvement (texte libre, formulaire, curseur de taille, verdict, taille limite, lancer l'analyse, comparer deux profils) ; Ajuster son plan (positions, règles, risque, frontière) ; Vérifier une preuve (liste des exécutions, registre, tiroir de source, audit, démonstration de sabotage) ; Explorer le monde (globe, filtres, fil, détail, « Brief me ») ; Rejouer l'histoire (date limite, mouvement, révélation) ; Comprendre le système (rôles, étapes) ; Créer un profil et consulter les sources.

## Fichiers principaux

- Styles : `web/src/styles/tokens.css`, `base.css`, `components.css`, `shell.css`, `dashboard.css`, `pages.css`, `motion.css` (+ nouveau `glass.css`, `tour.css`) ; `web/src/app/layout.tsx` (polices, `themeColor`), `web/src/lib/ui/theme.ts` (`themeColorFor`).
- Shell : `web/src/components/shell/AppShell.tsx` scindé en `TopBar.tsx`, `NavRail.tsx`, `SectionDock.tsx`, `CommandBar.tsx`, `SettingsMenu.tsx` ; `web/src/components/common/Page.tsx` (`PageHeader` avec actions, `Card`, nouveau `usePageSections`).
- Réutilisés tels quels : `useSlidingPill`, `SegmentedControl`, `Listbox`, `Drawer`, `FactDrawer`/`FactChip`, `DashboardGrid` + `lib/ui/layout.ts`, `LineChart`, `DonutChart`, `RollingText`, `readPref`/`writePref` (`lib/session.ts`), `tr()` (`state/app.tsx`).
- Accueil : `web/src/features/home/*` (disposition par défaut alignée sur le template ; KPI en tuiles ; donut avec barres de légende).
- Pages : `web/src/features/{portfolio,decision,audit,world,timemachine,system,profiles,sources}/*` (nettoyage + classes partagées + `data-tour` + sections du dock). Décider lit `?q=` pour préremplir le texte libre.
- Tutoriel : `web/src/features/tour/*`.
- Docs : `web/DESIGN.md` réécrit ; spec `docs/superpowers/specs/2026-11-15-liquid-glass-design.md` ; suivi `docs/superpowers/plans/2026-11-15-liquid-glass.md`.
- Tests : `web/tests/ui-logic.test.ts` (couleurs `themeColorFor`), `ui-contrast.test.ts` (jetons), nouveaux tests purs du moteur de tutoriel (placement, enchaînement, cible manquante) dans `web/tests/tour-logic.test.ts`.

## Checkpoints (commit + push sur `feat/liquid-glass` à chacun)

1. Branche, spec et suivi de progression dans le repo.
2. Fondations : jetons, polices, fond, matière verre, shell (barre du haut, barre de commande, rail, panneau de page, dock, disclaimer unique, réglages).
3. Composants partagés : cartes, boutons, segmentés, listes, tables + puces de filtre, statuts, tiroirs, états, graphiques.
4. Accueil façon template + nettoyage de l'Accueil.
5. Portefeuille, Décider, Preuves : nettoyage + style + sections.
6. Monde, Rejouer, Système, Profils, Sources : nettoyage + style + sections.
7. Moteur de tutoriel + visite de base + bouton Aide.
8. Tutoriels avancés.
9. DESIGN.md, tests, vérification complète, PR vers main.

Reprise après une coupure (limite de jetons) : le fichier de suivi dans le repo coche chaque étape et note la suivante ; il suffit de dire « continue » pour reprendre au bon endroit.

## Vérification

- À chaque checkpoint : `npm run typecheck`, `npm run test:contracts` (dans `web/`), `npm run build:web` (export statique).
- Navigateur intégré avec l'API locale (`.claude/launch.json` : `api` + `web`) : chaque page en clair et sombre, 375 / 768 / 1024 / 1440 px, rail replié/déplié, clavier (focus visible, Échap, flèches), réduit-mouvement et réduit-transparence, aucune erreur console ; captures d'écran comparées au template.
- Tutoriel : visite de base complète, chaque tutoriel avancé de bout en bout, cible manquante (drapeau éteint), rejouer depuis « ? », FR et EN.
- Fin : `npm run check` à la racine, puis PR vers main avec captures.
