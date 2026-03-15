# local/ — bundled Python packages

This directory holds the pip-installed Python packages required by the vklass skill (`requests`, `beautifulsoup4` and their dependencies).

## Purpose

When running inside a Kubernetes pod (e.g. `openclaw-zoe-0`) there is no pip available at runtime. Packages must already exist in the service user's `~/.local` directory. This folder is the portable, repo-tracked copy of those packages.

Python automatically finds packages installed here because `~/.local/lib/python*/site-packages` is on the default user site-packages path.

## Populating this directory

### Option A — copy from a running pod

```bash
kubectl exec -it openclaw-zoe-0 -n openclaw-zoe -- pip install requests beautifulsoup4
kubectl cp openclaw-zoe-0:/root/.local skills/vklass/local -n openclaw-zoe
# Adjust /root to the actual $HOME of the service user if different
```

### Option B — install locally

```bash
pip install --target skills/vklass/local/lib/python3/site-packages requests beautifulsoup4
```

## Deploying to the pod

Copy this directory to `$HOME/.local` of the OpenClaw service user inside the pod:

```bash
kubectl cp skills/vklass/local openclaw-zoe-0:/root/.local -n openclaw-zoe
```

## Persistence across pod restarts

`~/.local` **must** be backed by a Kubernetes PersistentVolume (PVC). Without a PVC the packages are lost on every pod restart. Add a volume mount similar to:

```yaml
# In the openclaw-zoe StatefulSet / Deployment spec:
volumeMounts:
  - name: home-local
    mountPath: /root/.local   # adjust to service user's $HOME/.local

volumes:
  - name: home-local
    persistentVolumeClaim:
      claimName: openclaw-zoe-home-local
```

Create the PVC before (re)deploying the pod, then copy the packages once — they will survive restarts.
