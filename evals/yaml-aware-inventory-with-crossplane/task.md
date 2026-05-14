# Inventory every OCI artifact a Crossplane management plane pulls

## Problem / Feature Description

A platform team running a Crossplane management plane has noticed
that their existing image-scanning pipelines miss the Crossplane
Provider, Function, and Configuration packages — those packages
carry their image reference under `.spec.package` on a
`pkg.crossplane.io/v1` `Provider` (or `Function`, or
`Configuration`) resource, not the conventional `image:` key on a
Pod spec. Their security audit needs a single artifact that lists
**every** OCI reference the chart pulls, regardless of whether it
appears as `image:` or `package:`.

The team also wants the inventory to discriminate properly:
unrelated `package:` keys (e.g. an npm-style `package.json` embedded
in a ConfigMap as part of bootstrap data) must NOT be flagged as a
Crossplane package. The inventory has to be YAML-aware, not a
naive grep, because grep would either over-catch (catching the
ConfigMap entry) or under-catch (missing the right `.spec.package`
when it isn't on a Crossplane resource).

The pre-rendered chart manifest is provided inline as a single
multi-document YAML file. The task is to produce an inventory file
that the team can hand to the next stage of their pipeline.

## Output Specification

Produce one file in the working directory:

- `inventory.json` — JSON array; one object per unique OCI
  reference. Each object must have at least:
  - `kind`: either `"container-image"` or `"crossplane-package"`
  - `ref`: the OCI image/package reference
  - `source_template`: which template in the rendered output
    produced this reference (taken from the `# Source:` comment
    that precedes the document in the YAML)

Deduplicate by `(kind, ref)`. Sort the array deterministically.

## Input Files

The following files are provided as inputs. Extract them before
beginning.

=============== FILE: inputs/rendered.yaml ===============
---
# Source: xp-mp/charts/crossplane/templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: crossplane
  namespace: crossplane-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: crossplane
  template:
    metadata:
      labels:
        app: crossplane
    spec:
      containers:
        - name: crossplane
          image: "xpkg.crossplane.io/crossplane/crossplane:v2.2.1"
---
# Source: xp-mp/charts/argo-cd/templates/redis/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: argocd-redis
  namespace: argocd
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
        - name: redis
          image: ecr-public.aws.com/docker/library/redis:8.2.3-alpine
---
# Source: xp-mp/templates/crossplane-providers.yaml
apiVersion: pkg.crossplane.io/v1
kind: Provider
metadata:
  name: provider-gcp-container
spec:
  package: xpkg.upbound.io/upbound/provider-gcp-container:v2.5.1
---
# Source: xp-mp/templates/crossplane-providers.yaml
apiVersion: pkg.crossplane.io/v1
kind: Function
metadata:
  name: function-patch-and-transform
spec:
  package: xpkg.crossplane.io/crossplane-contrib/function-patch-and-transform:v0.8.2
---
# Source: xp-mp/templates/bootstrap-configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: bootstrap-config
  namespace: argocd
data:
  package.json: |
    {
      "name": "bootstrap-tools",
      "version": "1.0.0",
      "dependencies": {
        "lodash": "4.17.21"
      }
    }
  description: |
    package: this is not a Crossplane package; it's a string in a multi-line block.
---
# Source: xp-mp/charts/argo-cd/templates/argocd-applicationset/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: argocd-applicationset-controller
  namespace: argocd
spec:
  replicas: 1
  selector:
    matchLabels:
      app: argocd-applicationset-controller
  template:
    metadata:
      labels:
        app: argocd-applicationset-controller
    spec:
      containers:
        - name: argocd-applicationset-controller
          image: quay.io/argoproj/argocd:v3.4.2
