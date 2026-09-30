# Brand asset provenance

`custom_components/velux_active/brand/icon.png` and `icon@2x.png` use an original
roof-window symbol created for this community integration. They are not VELUX
corporate logos and do not imply endorsement. The symbol and its renderer,
`scripts/brand.py`, are licensed under this repository's [MIT license](../LICENSE).
No external image, font, or trademark artwork was copied.

Reproduce both transparent PNG files with `uv run python scripts/brand.py`.
Home Assistant 2026.3 introduced custom integration local brand images. HACS
checks the local `brand/icon.png` before checking the remote brands repository.
