# gitops

Esto es lo que mira Argo CD. Si algo corre en `staging` o `prod` de Cauri vía Argo, hay un
`Application` acá que lo dice. Si lo cambiás en un cluster a mano y no está acá, Argo te lo va a
pisar en el próximo sync (`selfHeal: true` en todos). No hay atajos: el YAML de este repo es la
verdad, no lo que ves en el dashboard.

## Cómo bootstrapear un cluster nuevo

Una sola aplicación manual, después Argo se encarga de todo lo demás (patrón app-of-apps):

```
kubectl apply -f bootstrap/root.yaml
```

Eso crea dos `Application`: `root` (mira `apps/`, recursivo) y `root-projects` (mira `projects/`).
Las separé en dos porque `directory.include` con múltiples globs no anda igual en todas las
versiones de Argo 2.x que tenemos entre staging y prod, y prefiero dos Applications aburridas
que un include que funciona en un cluster y en el otro no. `root` va descubriendo cada
`apps/<app>/application-{staging,prod}.yaml` solo; no hace falta tocar `root.yaml` para sumar un
`Application` nuevo, alcanza con el commit en `apps/`.

## Cómo se promueve algo a prod

Depende de si la app es Helm o Kustomize:

- **Helm (payments-api, payments-worker, merchant-portal-bff, web-app, reporting-etl)**: el chart
  vive en el repo de la app, acá solo vive el `values-<env>.yaml`. El `build.yml` de cada app
  bumpea `apps/<app>/values-staging.yaml` en cada push a `main`, y `apps/<app>/values-prod.yaml`
  cuando se taggea `v*`. O sea: la promoción a prod la dispara un tag en el repo de la app, no un
  commit acá. Lo único que hacemos en `gitops` a mano es revisar el diff cuando el bot abre el PR
  (o directamente el commit si el pipeline pushea a `main`, según cómo lo tengan configurado en
  cada repo).
- **Kustomize (fraud-scoring, kyc-service)**: ahí ni siquiera tocamos este repo. El `build.yml` de
  cada app corre `kustomize edit set image` sobre su propio `deploy/overlays/staging` (o `prod` al
  taggear) y commitea al propio repo. Este repo solo tiene el `Application` que apunta al overlay;
  la imagen y el resto de la config quedan del lado de la app.

En los dos casos, Argo hace el sync solo (`automated: {prune: true, selfHeal: true}`) apenas ve el
commit. No hay un botón de "promote" en Argo: promover es taggear.

## Qué apps están en Argo y cuáles no

| App | En Argo | Estilo |
|---|---|---|
| payments-api | Sí | C — Helm, multi-source |
| payments-worker | Sí | C — Helm, multi-source |
| merchant-portal-bff | Sí | C — Helm, multi-source |
| web-app | Sí | C — Helm, multi-source |
| reporting-etl | Sí | C — Helm, multi-source |
| fraud-scoring | Sí | D — Kustomize, source único al overlay |
| kyc-service | Sí | D — Kustomize, source único al overlay |
| ledger-core | No | A — Actions + YAML pelado, `kubectl apply` directo |
| accounts-api | No | B — Actions + Helm, `helm upgrade --install` desde el runner |
| cards-api | No | B — Actions + Helm |
| mobile-bff | No | B — Actions + Helm |
| notifications | No | A — Actions + YAML pelado |
| backoffice (backoffice-api + backoffice-ui) | No | A — Actions + YAML pelado |
| fx-rates | No | E — manual (`deploy.sh`), sin workflow |

Migrar las de "No" a Argo está en el backlog. No es una prioridad urgente porque los estilos A y B
ya andan bien para lo que son (menos releases, menos entornos que sincronizar), pero cada vez que
alguien pierde media hora reconstruyendo a mano qué versión quedó en prod de una de esas, sumamos
un voto más a moverla acá.

## Estructura

```
bootstrap/root.yaml                  lo único que se aplica a mano
projects/cauri.yaml                  AppProject: qué repos y qué destinos puede tocar Argo acá
apps/<app>/application-staging.yaml  Application de Argo para staging
apps/<app>/application-prod.yaml     ídem para prod
apps/<app>/values-staging.yaml       solo en las 5 apps Helm
apps/<app>/values-prod.yaml          solo en las 5 apps Helm
```

Las apps Kustomize (fraud-scoring, kyc-service) no tienen `values-*.yaml` acá: su config por
entorno vive en el `deploy/overlays/{staging,prod}` de su propio repo. El `Application` de esas
dos apunta directo a ese path con un solo `source`, sin el segundo source de `gitops`.

## AppProject `cauri`

Un solo proyecto para todo. `sourceRepos` es un wildcard sobre la org
(`https://github.com/demo-org-np-migration/*`) porque cada app trae su propio chart u overlay y no
tiene sentido mantener una lista repo por repo acá. Los destinos son `staging` y `prod` en el
cluster local; no hay multi-cluster todavía.

## Antes de tocar esto

Si agregás una app nueva: copiá el patrón de una app existente del mismo estilo (Helm o
Kustomize), no inventes una estructura nueva. Si es Helm, el chart tiene que existir ya en el repo
de la app — leé su `values.yaml` antes de escribir el de acá, las claves tienen que calzar exacto
o Argo te va a tirar un values que no hace nada (Helm ignora silenciosamente una clave que no
existe en el chart, no te avisa).

Si vas a cambiar `resources` de algo en prod, mirá primero si hay un comentario arriba explicando
por qué está así. `reporting-etl` en prod tiene uno de un incidente de marzo que nadie revisó
todavía — no lo borres sin entender qué pasaba antes.
