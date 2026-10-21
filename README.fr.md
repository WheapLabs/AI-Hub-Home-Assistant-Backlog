# Backlog AI Hub pour Home Assistant

*[English version](README.md)*

Une intégration légère qui donne à vos automatisations et scripts Home
Assistant des **actions pour écrire dans le Backlog d'un
[AI Hub](https://github.com/WheapLabs)** : ajouter une tâche quand une pile est
faible, écrire au journal quand une sauvegarde échoue, cocher un point quand un
test réussit…

Elle ne garde **aucune copie** du Backlog. Chaque action est relayée au
service Backlog du hub (`POST /backlog-api/service`) et la réponse du hub
devient la réponse de l'action. Le Backlog ne vit qu'à un seul endroit : le hub.

## Ce qu'elle fait

- Des actions (domaine `backlog_aihub`), avec les mêmes champs et les mêmes
  réponses que la commande `aihub-backlog` du hub :

  | Action | Rôle | Réponse |
  |---|---|---|
  | `backlog_aihub.ajouter_tache` | Créer une tâche, ou compléter une tâche existante | `{rev, reponse: {id, items}}` |
  | `backlog_aihub.ajouter_journal` | Écrire une entrée au journal | `{rev, reponse: {id}}` |
  | `backlog_aihub.cocher` | Cocher / décocher des points (ou `tache:<id>`) | `{rev, reponse: null}` |
  | `backlog_aihub.repondre` | Répondre à un point « pas concluant » | `{rev, reponse: {item}}` |
  | `backlog_aihub.verifie` | Donner le résultat d'une loupe 🔍 | `{rev, reponse: {item, resultat}}` |
  | `backlog_aihub.decision_traitee` | Écrire la réponse à une décision | `{rev, reponse: {cible}}` |
  | `backlog_aihub.supprimer` | Supprimer une entrée d'une collection | `{rev, reponse: {supprime}}` |
  | `backlog_aihub.exporter` | Renvoyer tout le Backlog (réponse seulement) | les collections |

  C'est le hub qui vérifie chaque champ. S'il refuse (champ inconnu, point
  introuvable…), l'action échoue avec son message.
- Un capteur **À traiter** (`sensor.backlog_ai_hub_a_traiter` en français) :
  le nombre de choses qui attendent les agents (demandes, « pas concluants »,
  loupes 🔍, décisions), avec le détail en attributs (`demandes`, `a_revoir`,
  `a_verifier`, `decisions`, `maintenant`, `taches_ouvertes`, `rev`). Il relit
  le hub toutes les 2 minutes et juste après chaque action ; le hub répond
  « 304 » quand rien n'a changé.
- Configuration par l'interface : l'adresse du hub et le jeton du Backlog sont
  vérifiés avant l'ajout. On peut ensuite les modifier (« Reconfigurer ») ; si
  le jeton change, Home Assistant le redemande.

## Installation (HACS)

1. HACS → ⋮ → **Dépôts personnalisés** → ajouter
   `https://github.com/WheapLabs/AI-Hub-Home-Assistant-Backlog`, type **Intégration**.
2. Installer **Backlog AI Hub**, puis redémarrer Home Assistant.
3. Paramètres → Appareils et services → **Ajouter une intégration** →
   *Backlog AI Hub*.

Sans HACS : copier `custom_components/backlog_aihub` dans
`config/custom_components/` et redémarrer.

## Configuration

| Champ | Valeur |
|---|---|
| Adresse | L'API Backlog du hub, ex. `https://hub.example/backlog-api` (l'adresse du hub seule marche aussi : `/backlog-api` est ajouté) |
| Jeton du Backlog | Le jeton affiché dans la console du hub (ou `aihub-backlog jeton` sur le hub) |
| Vérifier le certificat TLS | À laisser coché ; à décocher seulement sur un réseau local de confiance |
| Fichier du certificat d'autorité | Facultatif : chemin de l'autorité du hub (ex. `/config/aihub-ca.crt`) quand le hub a la sienne |

## Exemples

```yaml
# Ajouter une tâche quand une pile est faible
- action: backlog_aihub.ajouter_tache
  data:
    id: "t-pile-{{ trigger.entity_id | replace('.', '-') }}"
    titre: "Changer la pile de {{ state_attr(trigger.entity_id, 'friendly_name') }}"
    prio: semaine
    type: reparer
    domaine: Appareils
    action: "Pile à {{ trigger.to_state.state }} %"

# Écrire au journal et lire la réponse du hub
- action: backlog_aihub.ajouter_journal
  data:
    titre: Sauvegarde échouée
    genre: constat
    domaine: Organisation
    pourquoi: "{{ trigger.event.data.message }}"
  response_variable: entree   # entree.reponse.id = l'identifiant de l'entrée

# Tout lire
- action: backlog_aihub.exporter
  response_variable: backlog
```

## Cohabiter avec une autre intégration Backlog

Le domaine est `backlog_aihub` : elle peut tourner à côté d'une ancienne
intégration au domaine `backlog`, le temps de basculer les automatisations.

## Plus tard : le panneau Backlog servi par le hub

Cette version n'ajoute pas de panneau. Le hub sert déjà les fichiers du
panneau (`GET /backlog-api/panneau/backlog-panel.js`) et applique ses messages
(`POST /backlog-api/action`, les mêmes messages `backlog/<action>` que le
panneau envoie par le WebSocket de Home Assistant). Une prochaine version
pourra :

1. déclarer un panneau de barre latérale (`panel_custom`) dont le module passe
   par une petite vue de Home Assistant qui relaie `/backlog-api/panneau/*`
   (le navigateur ne voit jamais le jeton) ;
2. déclarer les commandes WebSocket du panneau (`backlog/subscribe`,
   `backlog/fait`, …) et relayer chacune vers `POST /backlog-api/action`,
   `backlog/subscribe` étant nourri par la même lecture de
   `GET /backlog-api/donnees`.

Le code du panneau reste alors à un seul endroit (le hub) et sert à la fois
la console du hub et Home Assistant.

## Développement

Deux séries de tests :

```bash
# 1. Le client HTTP et les compteurs (sans Home Assistant)
python3 -m venv .venv && .venv/bin/pip install -r requirements_test.txt
.venv/bin/pytest
# Facultatif : test contre le vrai service du hub (lancé dans un dossier temporaire)
AIHUB_BACKLOG_SERVICE=/chemin/vers/AI-Hub/ct/bin/aihub-backlog .venv/bin/pytest

# 2. L'intégration dans Home Assistant (configuration, actions, capteur), Python 3.14
python3.14 -m venv .venv-ha && .venv-ha/bin/pip install -r requirements_test_ha.txt
.venv-ha/bin/pytest tests_ha
```

Le workflow GitHub lance les deux, plus les validations HACS et hassfest.

## Licence

MIT, voir [LICENSE](LICENSE).
