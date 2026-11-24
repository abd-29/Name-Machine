# Name Machine - Analyse exploratoire des données

**Périmètre :** Données françaises sur les prénoms, aux niveaux national, régional et départemental (1900–2025).  
**Source :** INSEE - Fichier des prénoms, édition 2025.  
**Fichiers analysés :** `names.csv`, `name_region.csv`, `name_dept.csv`.

## Dictionnaire des variables

Les fichiers présentent les effectifs de prénoms attribués à la naissance, ventilés par sexe, année et niveau géographique.

| Variable | Description | Valeurs / Exemple |
|---|---|---|
| `sexe` | Sexe de l'enfant à la naissance | `1` : garçon ; `2` : fille |
| `prenom` | Prénom attribué à la naissance | `GABRIEL`, `LOUISE`, `EMMA` |
| `periode` | Année de naissance | 1900 à 2025 |
| `valeur` | Effectif de naissances publié pour un prénom, un sexe, une année et un territoire | `4625` : GABRIEL en 2025 au niveau national |
| `rang` | Position du prénom dans le classement de popularité pour le sexe, l'année et le territoire considérés | `1` : premier du classement |
| `reg` | Code INSEE de la région, uniquement dans `name_region.csv` | `53` : Bretagne |
| `dpt` | Code INSEE du département, uniquement dans `name_dept.csv` | `35` : Ille-et-Vilaine |

**Granularité :**

- `names.csv` : prénom × sexe × année.
- `name_region.csv` : prénom × sexe × année × région.
- `name_dept.csv` : prénom × sexe × année × département.

## Synthèse

L'analyse porte sur **6 622 949 observations** réparties entre les trois fichiers INSEE, couvrant la période 1900–2025.

Les contrôles n'ont révélé aucun doublon sur les clés définies, aucun prénom manquant ni aucune valeur nulle ou négative dans les effectifs et les rangs.

Trois points nécessitent une attention particulière :

- Les effectifs publiés sont tous des multiples de 5, ce qui limite leur précision.
- Les données régionales et départementales ne reconstituent pas les effectifs nationaux lorsqu'elles sont agrégées.
- La couverture géographique varie selon les territoires et les périodes, notamment pour Mayotte.

## Inventaire et couverture

| Indicateur | National | Régional | Départemental |
|---|---:|---:|---:|
| Observations | 724 645 | 1 928 764 | 3 969 540 |
| Prénoms distincts | 49 163 | 27 213 | 17 671 |
| Années distinctes | 126 | 126 | 126 |
| Première année | 1900 | 1900 | 1900 |
| Dernière année | 2025 | 2025 | 2025 |
| Zones distinctes | — | 18 | 101 |
| Doublons sur les clés | 0 | 0 | 0 |
| Prénoms manquants | 0 | 0 | 0 |

Les 126 années sont représentées dans chacun des trois fichiers, mais la couverture temporelle n'est pas uniforme selon les territoires.

**Mayotte** apparaît à partir de 2012 dans les fichiers régional et départemental. Les autres territoires disposent d'observations sur l'ensemble de la période 1900–2025.

Le nombre de prénoms distincts diminue avec la granularité géographique : 49 162 au niveau national contre 17 671 au niveau départemental.

## Contrôles de qualité

Les vérifications ont porté sur les valeurs manquantes, les types de données, l'unicité des observations et la validité des effectifs.

| Contrôle | Résultat |
|---|---|
| Valeurs manquantes dans `sexe`, `periode`, `valeur`, `rang` | Aucune |
| Codes géographiques manquants | Aucun |
| Valeurs nulles ou négatives dans `valeur` | Aucune |
| Valeurs nulles ou négatives dans `rang` | Aucune |
| Doublons sur les clés | Aucun |
| Prénoms manquants | Aucun |

Les clés d'unicité utilisées sont :

- National : `(sexe, prenom, periode)`.
- Régional : `(sexe, prenom, periode, reg)`.
- Départemental : `(sexe, prenom, periode, dpt)`.

**Prénom textuel `NA` :** cette valeur valide du fichier national avait été interprétée comme manquante par la lecture CSV par défaut de pandas. L'import conserve désormais cette chaîne :

| Champ | Valeur |
|---|---:|
| `prenom` | `NA` |
| `sexe` | 2 |
| `periode` | 2003 |
| `valeur` | 5 |
| `rang` | 5 405 |

Cette observation est conservée dans les recherches, les statistiques et les contrôles de volume. Seuls les champs réellement vides sont traités comme manquants à l'import.

Les variables `reg` et `dpt` devront être importées comme des chaînes de caractères afin de préserver les codes géographiques, notamment `01`, `06`, `2A`, `2B` et `976`.

## Précision et comparabilité

### Précision des effectifs

L'ensemble des valeurs observées dans `valeur` sont des multiples de 5. Le plus petit effectif publié est égal à 5.

### Comparaison des niveaux géographiques

Les sommes des effectifs publiés en 2025 présentent des écarts.

| Niveau | Somme des `valeur` publiées | Écart par rapport au national |
|---|---:|---:|
| National | 589 485 | — |
| Régional | 528 105 | −10,4 % |
| Départemental | 440 630 | −25,3 % |

Les données régionales représentent ainsi environ 89,6 % du total national publié, contre 74,7 % pour les données départementales.

Ces écarts montrent que **l'agrégation des observations locales ne permet pas de reconstituer les effectifs nationaux**.

La moindre couverture des petits effectifs locaux constitue une explication possible, à confirmer dans la notice méthodologique INSEE.

En conséquence, les indicateurs nationaux seront calculés directement à partir de `names.csv`, sans agrégation des fichiers régionaux ou départementaux.

### Comparaison entre territoires

Une comparaison fondée uniquement sur les effectifs bruts favorise les territoires enregistrant un grand nombre de naissances.

Pour analyser la popularité géographique d'un prénom, deux indicateurs pourront être distingués :

- **Effectif publié :** nombre de naissances associé au prénom dans le territoire.
- **Part relative parmi les effectifs publiés :** rapport entre l'effectif du prénom et la somme des effectifs publiés pour le sexe, l'année et le territoire considérés.

Le second indicateur facilite les comparaisons géographiques, mais ne représente pas nécessairement la proportion exacte de toutes les naissances.

## Contrôle métier (Année 2025)

### Prénoms les plus populaires

| Sexe | Rang 1 | Effectif | Rang 2 | Effectif | Rang 3 | Effectif |
|---|---|---:|---|---:|---|---:|
| Garçons | GABRIEL | 4 625 | NOAH | 3 465 | LÉO | 3 420 |
| Filles | LOUISE | 3 070 | JADE | 2 925 | AMBRE | 2 805 |

### Évolution des effectifs publiés

Sommes annuelles calculées sur le fichier national :

| Année | Effectifs publiés |
|---|---:|
| 1900 | 412 710 |
| 1950 | 881 650 |
| 2000 | 777 295 |
| 2025 | 589 485 |


## Conséquences pour l'application Dash

| Module | Source | Règle de traitement |
|---|---|---|
| Time Machine | National | Évolution annuelle par prénom et sexe ; signalement des années non publiées |
| Name Battle | National | Comparaison de deux prénoms sur une même période et selon un indicateur identique |
| Name Explorer | Régional / départemental | Comparaison géographique avec indicateurs et couverture explicités |
| Hall of Fame | National | Classements et records calculés à partir des observations nationales |

### Préparation des données

Les opérations retenues sont les suivantes :

1. Conserver les trois fichiers CSV sources sans modification.
2. Vérifier les schémas, les types et les clés à chaque chargement.
3. Préserver les prénoms textuels, notamment `NA`, sans les convertir en valeurs manquantes.
4. Maintenir les codes géographiques sous forme de chaînes.
5. Ajouter les noms et contours des régions et départements.
6. Convertir les fichiers en Parquet pour optimiser leur exploitation dans Dash.
7. Vérifier les volumes et les agrégations après transformation.

## Points 

| Sujet | Risque identifié | Mesure retenue |
|---|---|---|
| Couverture locale | Absence d'un prénom dans certains territoires ou certaines années | Distinguer absence de donnée publiée et effectif nul |
| Précision statistique | Effectifs publiés différents des nombres exacts | Documenter les règles de diffusion INSEE |
| Mayotte | Absence de données locales avant 2012 | Adapter les périodes disponibles aux territoires |
| Comparaison géographique | Biais lié au volume des naissances | Proposer des effectifs et des indicateurs relatifs |
| Agrégation | Totaux locaux inférieurs au national | Ne pas reconstituer le national à partir des données locales |
| Traçabilité | Perte des règles de transformation | Conserver les sources, la documentation et les contrôles reproductibles |

## Conclusion

L'analyse exploratoire valide l'utilisation des trois fichiers INSEE pour le développement de **Name Machine**.

Aucun problème majeur de structure ou d'intégrité n'a été identifié. Les principales limites concernent la précision des effectifs publiés, leur couverture locale et la comparabilité entre niveaux géographiques.


---

**Référence technique :** `data/data_analysis.ipynb`  
**Source statistique :** INSEE — Fichier des prénoms, édition 2025.
