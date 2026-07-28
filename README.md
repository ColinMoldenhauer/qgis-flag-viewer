# Flag Viewer (QGIS plugin)

A QGIS plugin that samples the raster band value under the mouse cursor —
like [Value Tool](https://github.com/jorgealmerio/valuetool) — but decodes
it into its [CF `flag_meanings`](https://cfconventions.org/cf-conventions/cf-conventions.html#flags)
instead of showing the raw digital number.

Status: **early draft / untested in a live QGIS session.** The core
decoding logic is unit tested and dependency-free; the QGIS-facing widget
code follows standard plugin patterns but hasn't been run inside QGIS yet.

## Layout

```
flag_viewer/              the installable plugin package
  core/                    pure-Python decoding logic (no QGIS/GDAL import at module load time)
    flag_decoder.py        FlagDefinition: categorized + bitmask decode()
    cf_metadata.py         auto-detect flag_values/flag_masks/flag_meanings via GDAL band metadata
    mapping_io.py          load/save a mapping as JSON or YAML
    layer_property.py      load/save a mapping as a QGIS layer custom property (project-embedded)
  metadata.txt             QGIS plugin manifest
  flag_viewer_plugin.py    main plugin class (toolbar action, menu, wiring)
  flag_map_tool.py         QgsMapTool that reports the cursor's map position
  flag_dock_widget.py      dock widget showing layer/band/value/meaning(s)
  mapping_dialog.py        GUI editor for a manual mapping
tests/                     unit tests for flag_viewer.core (no QGIS required)
scripts/deploy_dev.ps1     symlinks flag_viewer/ into your QGIS profile for local dev
```

## Running the tests

```
pip install -r requirements-dev.txt
pytest
```

These only exercise `flag_viewer/core`, which has no QGIS dependency, so
they run in a plain Python environment — no QGIS install required.

## Trying it in QGIS

1. Install QGIS's Python deps aren't needed beyond what QGIS already
   ships (PyQt, `qgis.core`, `qgis.gui`; `osgeo.gdal` is optional and only
   used for auto-detection).
2. From a PowerShell prompt: `pwsh -File scripts/deploy_dev.ps1` to symlink
   `flag_viewer/` into your QGIS profile's plugin folder (requires
   Developer Mode or admin rights to create symlinks on Windows).
3. In QGIS: Plugins > Manage and Install Plugins > Installed, enable
   "Flag Viewer".
4. Load a raster with CF flag attributes (e.g. a NetCDF/HDF5 file opened
   through GDAL), click the Flag Viewer toolbar icon, and move the mouse
   over the raster. If auto-detection doesn't find a mapping, use
   Raster > Flag Viewer > Load/Edit Flag Mapping. A mapping loaded or
   edited this way is saved onto the layer and survives closing and
   reopening the project — no need to keep a sidecar file around or
   re-load it every session. Raster > Flag Viewer > Clear Flag Mapping
   removes it again.

No data handy? [sample_data/](sample_data/) has four tiny 4x4 rasters
(2 GeoTIFF, 2 NetCDF) covering both flag modes and both the auto-detect
and manual-mapping paths — see [sample_data/README.md](sample_data/README.md).

Not yet verified end-to-end in a running QGIS instance — treat this as a
first pass to react to and iterate on, not a finished plugin.

## Roadmap to the official QGIS plugin repository

Not submitted yet. Rough path to [plugins.qgis.org](https://plugins.qgis.org):

1. **Verify in a live QGIS session** (see above) — auto-detection, manual
   mapping load/edit, and the dock widget all need to actually work
   before anything else matters.
2. **Push this repo to its public GitHub home.** `metadata.txt` already
   points at `github.com/ColinMoldenhauer/qgis-flag-viewer` (matching the
   `origin` remote); the repo itself isn't public yet.
3. **Package and validate** — done via [qgis-plugin-ci](https://github.com/qgis/qgis-plugin-ci)
   (config in `pyproject.toml`'s `[tool.qgis-plugin-ci]`).
   `.github/workflows/package.yml` runs on every push/PR and packages
   `flag_viewer/` into a zip as a build check (nothing published);
   `.github/workflows/release.yml` attaches that zip to a GitHub Release
   once one is published. Publishing straight to plugins.qgis.org via the
   same tool (`--osgeo-username`/`--osgeo-password`) is left commented out
   in `release.yml` until after step 4 below.
4. **Create a QGIS plugins.qgis.org account** and submit the zip through
   the web form — this reads `metadata.txt` for the listing details. (Or,
   once you have an OSGeo account, add `OSGEO_USER`/`OSGEO_PASSWORD` as
   repo secrets and uncomment the publish step in `release.yml` to do
   this automatically on release.)
5. **Pass initial review**: first-time submissions are reviewed manually
   by the QGIS plugin approval team (install/run sanity check, license
   check, no obvious malicious/unsafe code) before appearing publicly.
6. **Ship as `experimental=True`** (already set) for early users, then
   flip to stable once it's proven itself across a few versions and
   real-world rasters.
7. **Iterate via version bumps**: each new `version` in `metadata.txt`,
   tagged and released on GitHub, is what `release.yml` packages and
   ships to users who already installed it.
