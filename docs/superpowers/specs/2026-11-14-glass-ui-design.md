# Refonte UI « Glass » d'Aplomb — design

**Date :** 2026-11-14 · **Périmètre web :** `web/` (Next.js 16, React 19, export statique) · **Référence visuelle :** [Glassy Dashboard V18](assets/2026-11-14-glassy-dashboard-reference.webp), fourni par l'utilisateur (panneaux de verre dépoli flottants sur un fond d'ambiance chaud, KPI en tuiles avec icône, graphique en barres, donut, classement, entonnoir, colonne de cartes à droite dont une accentuée en bleu). On s'en inspire pour l'ambiance, la densité et les proportions ; on n'en reprend ni les données ni la photo de fond.

## 1. Intention

Rendre le site Aplomb nettement plus beau et plus agréable à utiliser pour la démo du datathon : un dashboard « glassy » animé, fluide, qui **n'augmente pas la charge mentale**. Le fond du produit ne change pas : chiffres calculés par le code, chaque chiffre relié à sa source (FactChip), statuts jamais portés par la couleur seule, disclaimer « simulation » toujours visible.

## 2. Objectifs, non-objectifs, anti-objectifs

**Objectifs**
- Nouveau design system « verre » appliqué à tout le site : shell (sidebar, topbar), cartes, boutons, champs, tableaux, badges, drawers, états (chargement/erreur/vide).
- **Deux thèmes, sombre et clair**, avec bascule. Par défaut : préférence système ; le choix manuel est mémorisé (préférence UI locale, autorisée par `web/SPEC.md` §2).
- **Home reconstruite en dashboard** inspiré de l'image, avec uniquement des données réelles de l'API.
- Animations utiles et calmes : entrées discrètes, pastille glissante sur les sélecteurs, chiffres qui « roulent », tracé du graphique, drawer qui glisse.
- Fluide : 60 fps visés, pas de saccade au scroll, poids JS ajouté raisonnable.

**Non-objectifs**
- Pas de refonte de la *mise en page* de Portfolio, Decision Desk, Evidence & Audit, Sources, Profiles : elles héritent du nouveau look via les classes partagées, sans changer leur structure ni leur logique.
- Aucun changement backend, contrats, API client, logique d'état (`state/`, `lib/`, `api/`).

**Anti-objectifs (échec même si « ça marche »)**
- Un chiffre inventé ou décoratif (l'image montre des données de CRM : on ne les recopie pas).
- Du texte illisible sur le verre (contraste < WCAG AA), dans un des deux thèmes.
- Des animations en boucle qui distraient, ou qui ignorent `prefers-reduced-motion`.
- Un site qui rame (flou empilé partout, animations de layout coûteuses).
- Casser le clavier, le focus, le drawer accessible, la vue mobile, ou les tests existants.

## 3. Contraintes

- `web/DESIGN.md` et `web/SPEC.md` restent la loi : cibles 44 px, focus doré visible, Escape/focus-trap des drawers, alternative tableau pour les graphiques, unités et légendes hors tooltip, disclaimer persistant, `dataAsOf` près de l'en-tête, aucune injection de texte de modèle en HTML, export statique (pas de runtime serveur).
- Pas d'appel réseau au build : les polices passent par des fichiers locaux.
- Dépendances en versions exactes, comme le reste du repo ; `npm run typecheck` et `npm run test:contracts` doivent rester verts, ainsi que `next build`.
- `web/DESIGN.md` est le contrat design de l'équipe : il sera mis à jour pour décrire les nouveaux tokens et thèmes.

## 4. Approches envisagées

| Approche | Pour | Contre |
|---|---|---|
| **A. CSS pur + `motion` pour les seules animations de layout (choisie)** | Garde l'architecture actuelle (CSS global + variables) ; Arc library (MIT) suit exactement ce modèle, ses tokens de mouvement se transposent tels quels ; `motion` ne sert qu'aux pastilles glissantes et aux transitions d'entrée/sortie | Une dépendance de plus (~30–40 ko gz) |
| B. Tailwind + composants shadcn copiés (Kokonut, etc.) | Copier-coller rapide de composants | Réécriture de toutes les classes de l'app, deux systèmes de style en parallèle, gros diff sur des fichiers d'autres tracks |
| C. 100 % CSS, sans librairie d'animation | Zéro dépendance | Pastilles glissantes et sorties animées (drawer) maladroites ; plus de code maison fragile |

Thème : l'utilisateur a choisi **sombre + clair avec bascule** (plutôt que sombre seul ou clair seul). Périmètre : **design system complet + Home en dashboard** (plutôt que refaire toutes les pages ou seulement shell + Home).

## 5. Décisions de design

### 5.1 Thèmes et tokens
- Attribut `data-theme="dark|light"` sur `<html>`, posé par un petit script inline avant le premier rendu (pas de flash) ; sans choix enregistré → `prefers-color-scheme`.
- Identité conservée : navy `#0F2233`, teal `#0B5E66`, or `#E3A53B`, Fraunces (titres et grands chiffres), IBM Plex Sans (UI), IBM Plex Mono (chips de preuve).
- **Sombre** : fond navy très profond avec 3 halos flous (teal, or, bleu) ; verre = blanc 6–10 % d'opacité, `backdrop-filter: blur(22px) saturate(150%)`, bordure blanche 10–14 %, reflet interne en haut ; texte blanc 92 %, secondaire 64 %.
- **Clair** : fond gris-bleu clair avec halos pastel ; verre = blanc 55–70 %, même flou, bordure blanche 70 % + ombre douce ; texte = encre actuelle.
- Couleurs de statut (pass/tension/conflict/nee) redéfinies par thème pour garder AA ; toujours icône + texte.
- `@supports not (backdrop-filter)` et `prefers-reduced-transparency` → surfaces opaques.
- Rayons : panneau 24 px, carte 20 px, contrôle 12 px, pilule 999 px. Ombres « flottantes » douces.

### 5.2 Mouvement (tokens repris d'Arc library, MIT)
- Ressorts : `snappy` (visualDuration 0.26, bounce 0) pour les pastilles, `smooth` (0.4) pour les panneaux.
- Easing d'entrée `cubic-bezier(0.16, 1, 0.3, 1)`, de sortie `cubic-bezier(0.7, 0, 0.84, 0)` ; durées 120 / 160 / 240 / 480 ms.
- Entrée de page : fondu + montée de 8 px, cartes décalées de 40 ms, une seule fois par affichage.
- Chiffres KPI : roulement chiffre par chiffre (style odomètre, CSS) à l'affichage et quand la valeur change ; texte réel exposé aux lecteurs d'écran.
- Graphique : tracé qui se dessine (≈700 ms) puis aire en dégradé qui apparaît ; survol = réticule + infobulle.
- Survol/pression : couleur et lueur uniquement, pas de zoom (règle Kokonut/Arc) ; boutons : légère pression 0.98.
- Fond d'ambiance : dérive très lente des halos (≥ 40 s), transform uniquement ; **coupée** en `prefers-reduced-motion`, comme toutes les autres animations (qui deviennent instantanées).

### 5.3 Shell
- **Sidebar** en panneau de verre flottant (marge 12 px, rayon 24 px) : logo, carte de l'investisseur fictif (avatar, nom, « Investisseur fictif »), navigation avec icônes (lucide), pastille active qui glisse d'un lien à l'autre, pied : Sources, version de données.
- **Topbar** en verre : sélecteur d'investisseur, **fenêtre en segmented control** à pastille glissante (Full / 1Y / 3Y / 5Y / YTD) à la place du `<select>`, EN/FR (si activé), **bascule de thème**, « Données au … ».
- Disclaimer : bandeau fin en verre teinté or, toujours visible.
- Mobile < 768 px : sidebar masquée, bouton Menu → drawer gauche (existant, restylé et animé).

### 5.4 Home = dashboard (données réelles uniquement)
Correspondance avec l'image :

| Image | Aplomb (source API) |
|---|---|
| En-tête « Reports » + Export | Nom du profil + résumé (capital, horizon, risque, objectif, fenêtre) + « Tester un mouvement » / « Examiner le plan » |
| 4 KPI | 5 tuiles : valeur fictive, YTD, 1 an, volatilité, baisse max — chaque valeur reste un FactChip cliquable (`overview`) |
| Graphique Revenue | Historique à pondérations constantes, aire en dégradé + benchmark pointillé, bouton « tableau » conservé (`performance`) |
| Donut Lead sources | Allocation par grand groupe d'actifs (`snapshot.byAssetGroup`) + bascule Pays (`byCountry`), légende avec % visibles |
| Leaderboard | Principales positions (`concentration.topPositions`) : poids en barre, rendement 1 an |
| Conversion funnel | Santé du plan : verdict + barres par statut (`counts`) + règles avec marge restante (`ruleChecks.headroom`) |
| Colonne droite (Contacts / Credits / Texts) | Carte investisseur accentuée (dégradé teal), rendements 3 et 5 ans, stress 2022 (`returns`, `risk`) |
| — | Note d'analyse (agent) en bas, inchangée côté logique ; indisponible en local → état d'erreur propre |

Grille : ≥ 1440 px, colonne principale + colonne droite de 320 px ; 1100–1440 px, colonne droite repliée sous la grille ; < 768 px, une colonne.

### 5.5 Composants
- Restylage CSS (pas de changement de logique) : `.card`, `.btn*`, `.pill`, `.vbadge`, `.chip`, `.data-table`, champs, `.state*`, `.drawer`, `.tile`, `.bars`, `.scenario`, `.hero`, `.stale-note`, timeline.
- Nouveaux composants dans `web/src/components/ui/` : `AmbientBackground`, `ThemeToggle`, `SegmentedControl`, `RollingText` (roulement), `Reveal` (entrée décalée), `DonutChart` (SVG + légende/tableau accessible), `Skeleton` (chargement shimmer).
- `LineChart` : même API, rendu enrichi (dégradé, tracé animé, réticule) ; `SeriesTable` inchangé.
- Icônes : `lucide-react` (ISC). Polices locales : paquets `@fontsource` (OFL) pour Fraunces, IBM Plex Sans, IBM Plex Mono.
- Dépendances ajoutées (versions exactes) : `motion` 14.14.0, `lucide-react` 1.73.0, `@fontsource-variable/fraunces` 5.3.0, `@fontsource/ibm-plex-sans` 5.3.0, `@fontsource/ibm-plex-mono` 5.3.0. L'utilisateur a validé l'ajout le 2026-11-14 et se charge de prévenir T01, propriétaire de `web/package.json` et du lockfile.

### 5.6 Performance
- Flou réservé aux panneaux (sidebar, topbar, cartes) ; jamais de flou imbriqué sur les éléments internes (tuiles, lignes de tableau = teinte simple).
- Halos d'ambiance = dégradés radiaux sur un calque fixe, animés en `transform` seulement.
- `motion` limité aux composants qui en ont besoin (client components), pas d'animation de layout sur les grandes listes/tableaux.

### 5.7 Chiffres et preuves sur la Home
- Toute valeur qui a un `factId` dans la réponse reste un **FactChip** cliquable (valeur, rendements, volatilité, baisse max, stress 2022, valeurs/seuils de règles).
- Les valeurs d'affichage sans `factId` (poids d'allocation, poids et rendement 1 an des principales positions, marge des règles) sont montrées en texte simple, comme la page Portfolio le fait déjà. HOME-04 vise les chiffres **générés** (prose des agents), qui restent inchangés.
- Roulement des chiffres : `useQuery` vide volontairement les données quand la clé change (WEB-04, pas de chiffres périmés). Les KPI passent donc par un squelette shimmer pendant le chargement, puis roulent depuis zéro à l'arrivée des nouvelles données. On n'affiche jamais l'ancien chiffre pendant une transition.

### 5.8 Livraison par incréments
Le rendu vidéo est prévu lundi 16 novembre 14:00 (`docs/08-DELIVERABLES.md`). Chaque incrément doit être livrable seul, sans casser les parcours existants, notamment Decision Desk, qui est le cœur de la vidéo :
1. Tokens + thèmes sombre/clair + bascule + fond d'ambiance + restylage CSS des composants partagés (tout le site change de look d'un coup).
2. Shell : sidebar et topbar en verre, segmented control de fenêtre, menu mobile.
3. Home dashboard.
4. Mouvement : roulement des chiffres, tracé du graphique, entrées décalées, drawer animé.
5. Finitions : SVG des autres pages (frontière Portfolio) qui suivent le thème, contrastes, mobile.
En cas de manque de temps, on coupe dans l'ordre inverse : 5, puis 4. Les incréments 1 à 3 forment le minimum.

## 6. Vérification
- Visuelle dans le navigateur local, thèmes sombre et clair, à 375 / 768 / 1440 px.
- Contraste AA des textes principaux, secondaires et badges, dans les deux thèmes.
- Clavier : skip link, nav, segmented control (flèches), drawers (Escape, retour du focus).
- `prefers-reduced-motion` : aucune animation non essentielle.
- `npm run typecheck`, `npm run test:contracts`, `next build` (export statique) verts.

## 7. Laissé au builder
Valeurs exactes d'opacité, de flou et de couleurs des halos (dans le cadre AA ci-dessus), choix des icônes, micro-détails de layout, ordre d'implémentation.
