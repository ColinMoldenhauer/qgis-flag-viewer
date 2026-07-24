# Flag Viewer (QGIS plugin)

A QGIS plugin that samples the raster band value under the mouse cursor —
like [Value Tool](https://github.com/jorgealmerio/valuetool) — but decodes
it into its [CF `flag_meanings`](https://cfconventions.org/cf-conventions/cf-conventions.html#flags)
instead of showing the raw digital number.

Status: **early draft / untested in a live QGIS session.** The core
decoding logic is unit tested and dependency-free; the QGIS-facing widget
code follows standard plugin patterns but hasn't been run inside QGIS yet.
See [DESIGN.md](DESIGN.md) for the reasoning behind the architecture,
including why this is a standalone plugin rather than a fork of Value
Tool, and how flag mapping detection/input is meant to work.

## Layout

```
flag_viewer/              the installable plugin package
  core/                    pure-Python decoding logic (no QGIS/GDAL import at module load time)
    flag_decoder.py        FlagDefinition: categorized + bitmask decode()
    cf_metadata.py         auto-detect flag_values/flag_masks/flag_meanings via GDAL band metadata
    mapping_io.py          load/save a mapping as JSON or YAML
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
   Raster > Flag Viewer > Load/Edit Flag Mapping.

Not yet verified end-to-end in a running QGIS instance — treat this as a
first pass to react to and iterate on, not a finished plugin.
