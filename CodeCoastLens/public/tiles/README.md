# Map tiles

Each layer lives in its own folder named after its `id` in `../data/layers.json`:

```
tiles/<layer-id>/{z}/{x}/{y}.png
```

Generate them with `scripts/tiles/make_tiles.py` (see the repo's `scripts/README.md`).
After a layer's tiles are here, set its `status` to `"ready"` in `layers.json`.
