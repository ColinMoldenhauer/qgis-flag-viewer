# Flag Viewer (QGIS plugin)

A QGIS plugin that samples the raster band value under the mouse cursor —
like [Value Tool](https://github.com/jorgealmerio/valuetool) — but decodes
it into its [CF `flag_meanings`](https://cfconventions.org/cf-conventions/cf-conventions.html#flags)
instead of showing the raw digital number.

Status: **verified in a live QGIS session, not yet published.** The core
decoding logic is unit tested and dependency-free; auto-detection, manual
mapping load/edit, and the dock widget have all been exercised end-to-end
in QGIS. Marked `experimental=True` in `metadata.txt` pending its first
release.

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

## Supported flag mapping sources

A mapping is what turns a raw band value into one or more meanings. CF
conventions define three shapes, all handled by `flag_viewer/core/flag_decoder.py`:

| Attributes | Mode | Semantics |
|---|---|---|
| `flag_values` only | categorized | value equals exactly one `flag_values[i]` -> exactly one meaning |
| `flag_masks` only | bitmask | `(value & flag_masks[i]) != 0` per meaning -> zero, one, or several meanings |
| `flag_masks` + `flag_values` | bitmask with multi-bit fields | `(value & flag_masks[i]) == flag_values[i]` per meaning |

Regardless of shape, Flag Viewer resolves *where* that mapping comes from
per raster layer, trying each of the following in order (when the toolbar
icon is toggled on):

1. **Layer custom property** — a mapping already stored on the layer from
   an earlier Load/Edit in this or a previous session
   (`flag_viewer/core/layer_property.py`). Saved onto the `.qgz`/`.qgs`
   project file itself, so it survives closing and reopening the project
   with no sidecar file to keep track of.
2. **CF metadata auto-detection** (`flag_viewer/core/cf_metadata.py`) —
   reads `flag_values`/`flag_masks`/`flag_meanings` straight from the
   raster's own GDAL band metadata. Works for **NetCDF/HDF5** sources,
   since GDAL copies CF attributes into band metadata for those formats.
   Does **not** work for plain **GeoTIFF** and most other formats, which
   have no standard place to carry these attributes — expected, not a
   bug.
3. **User-supplied mapping**, when the above finds nothing:
   - **Load Flag Mapping...** loads a JSON or YAML sidecar file
     (`flag_viewer/core/mapping_io.py`) — the right choice when the
     mapping is already known (e.g. from a sensor's documentation) and
     can be written or generated outside QGIS. Shape:
     ```json
     {
       "flag_meanings": ["cloud", "shadow", "snow"],
       "flag_masks": [1, 2, 4]
     }
     ```
     (use `"flag_values"` instead of/alongside `"flag_masks"` for the
     other two modes above).
   - **Edit Flag Mapping...** opens a GUI table editor (value/mask ->
     meaning rows, categorized/bitmask choice) for building a mapping by
     hand with no file to write first; its "Save to file..." button
     exports the same JSON/YAML shape.

Mappings supplied via Load or Edit are written back onto the layer's
custom property automatically, so they become source 1 on the next
session. Auto-detected mappings are *not* persisted this way, since
they're cheap to rediscover from the file itself. **Clear Flag Mapping**
removes both the in-memory mapping and the stored custom property for
the active layer.

## Plugin functionality

The toggle gets an icon on QGIS's Plugins toolbar; that's the only entry
point outside the dock widget itself — deliberately not also registered
under the Raster/Mesh menus, to avoid cluttering those with per-plugin
commands. Load/Edit/Clear/Lock each get an icon inside the Flag Viewer dock
widget's own toolbar (visible once the dock is shown via the toggle).

| Command | Path | What it does |
|---|---|---|
| Flag Viewer (toggle) | Plugins toolbar icon | Turns hover-sampling on/off. On enable: auto-detects/loads a mapping for every raster layer in the project (skipping layers that already have one) and shows the dock widget reporting layer/band/value/meaning(s) under the cursor. On disable: hides the dock widget and disengages the map tool. |
| Load Flag Mapping... | Icon in the dock widget toolbar | Loads a JSON/YAML sidecar mapping file for the active raster layer and stores it on the layer. |
| Edit Flag Mapping... | Icon in the dock widget toolbar | Opens the GUI table editor to build or modify a mapping for the active raster layer by hand; stores the result on the layer. |
| Clear Flag Mapping | Icon in the dock widget toolbar | Removes the in-memory mapping and the stored custom property for the active raster layer. |

Load/Edit/Clear all act on the current `activeLayer()` — select a raster
layer first, or the plugin shows a warning asking you to.

A **Layers** dropdown in the dock widget's toolbar controls which layers are
sampled under the cursor: **All** (every layer in the project, the default),
**Visible** (layers currently checked on in the Layers panel), or **Selected**
(layers currently highlighted in the Layers panel). The choice is remembered
across QGIS sessions.

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
   over the raster. If auto-detection doesn't find a mapping, use the
   Load/Edit Flag Mapping icons in the dock widget's toolbar — see
   [Supported flag mapping sources](#supported-flag-mapping-sources) and
   [Plugin functionality](#plugin-functionality) above for what each
   command does.

No data handy? [sample_data/](sample_data/) has four tiny 4x4 rasters
(2 GeoTIFF, 2 NetCDF) covering both flag modes and both the auto-detect
and manual-mapping paths — see [sample_data/README.md](sample_data/README.md).
