# ADMET-AI (admet_agent.py)

- Container: `../selectisafe/builds/admet-ai.sif`
- Source: https://github.com/swansonk14/admet_ai — image built from Docker Hub
  `dhanus12/admet-ai:latest` (a third-party repackaging; confirmed from the container's
  OCI labels, which also confirm the entrypoint is `admet_predict` on PATH)
- Role in the pipeline: predicts ADMET (absorption/distribution/metabolism/excretion/
  toxicity) properties for each generated molecule's SMILES.

## Verified against the real source

Fetched the repo's `README.md` directly from GitHub. Its documented CLI example is:

```bash
admet_predict \
    --data_path data.csv \
    --save_path preds.csv \
    --smiles_column smiles
```

— an exact match for the command this pipeline already builds in
`admet_agent._build_command`; nothing needed to change here, unlike aizynthfinder.

## What is still unconfirmed

Whether `admet_predict` passes non-`smiles` input columns (like our `complex_name`)
through to the output CSV. The README's Python-API section says predictions come back
indexed by SMILES, which suggests the CLI output may also key on `smiles` alone rather
than preserving other input columns — `admet_agent.run()` already falls back to keying
its result dict by `smiles` if `complex_name` isn't a column in the output.

## Command this pipeline runs

```bash
apptainer exec admet-ai.sif admet_predict \
    --data_path <smiles.csv> --smiles_column smiles --save_path <out.csv>
```

## Standalone smoke test

```bash
printf "smiles\nCC(=O)Oc1ccccc1C(=O)O\n" > /tmp/aspirin.csv
apptainer exec ../selectisafe/builds/admet-ai.sif admet_predict \
    --data_path /tmp/aspirin.csv --smiles_column smiles --save_path /tmp/admet_smoke_test.csv
```

CPU-only — no `--nv` needed; the README notes a GPU is used automatically if available
but is not required.
